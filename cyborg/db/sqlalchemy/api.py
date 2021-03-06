# Copyright 2017 Huawei Technologies Co.,LTD.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""SQLAlchemy storage backend."""

import threading
import copy
import uuid

from oslo_db import api as oslo_db_api
from oslo_db import exception as db_exc
from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy import utils as sqlalchemyutils
from oslo_log import log
from oslo_utils import strutils
from oslo_utils import timeutils
from oslo_utils import uuidutils
from sqlalchemy.orm import load_only
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func


from cyborg.common import exception
from cyborg.common.i18n import _
from cyborg.db import api
from cyborg.db.sqlalchemy import models
from sqlalchemy import or_
from sqlalchemy import and_

_CONTEXT = threading.local()
LOG = log.getLogger(__name__)
MYLOG = LOG

main_context_manager = enginefacade.transaction_context()


def get_backend():
    """The backend is this module itself."""
    return Connection()


def _session_for_read():
    return enginefacade.reader.using(_CONTEXT)


def _session_for_write():
    return enginefacade.writer.using(_CONTEXT)


def get_session(use_slave=False, **kwargs):
    return main_context_manager._factory.get_legacy_facade().get_session(
        use_slave=use_slave, **kwargs)


def model_query(context, model, *args, **kwargs):
    """Query helper for simpler session usage.

    :param context: Context of the query
    :param model: Model to query. Must be a subclass of ModelBase.
    :param args: Arguments to query. If None - model is used.

    Keyword arguments:

    :keyword project_only:
      If set to True, then will do query filter with context's project_id.
      if set to False or absent, then will not do query filter with context's
      project_id.
    :type project_only: bool
    """

    if kwargs.pop("project_only", False):
        kwargs["project_id"] = context.tenant

    with _session_for_read() as session:
        query = sqlalchemyutils.model_query(
            model, session, args, **kwargs)
        return query


def add_identity_filter(query, value):
    """Adds an identity filter to a query.

    Filters results by ID, if supplied value is a valid integer.
    Otherwise attempts to filter results by UUID.

    :param query: Initial query to add filter to.
    :param value: Value for filtering results by.
    :return: Modified query.
    """
    if strutils.is_int_like(value):
        return query.filter_by(id=value)
    elif uuidutils.is_uuid_like(value):
        return query.filter_by(uuid=value)
    else:
        raise exception.InvalidIdentity(identity=value)


def _paginate_query(context, model, limit, marker, sort_key, sort_dir, query):
    sort_keys = ['id']
    if sort_key and sort_key not in sort_keys:
        sort_keys.insert(0, sort_key)
    try:
        query = sqlalchemyutils.paginate_query(query, model, limit, sort_keys,
                                               marker=marker,
                                               sort_dir=sort_dir)
    except db_exc.InvalidSortKey:
        raise exception.InvalidParameterValue(
            _('The sort_key value "%(key)s" is an invalid field for sorting')
            % {'key': sort_key})
    return query.all()


class Connection(api.Connection):
    """SqlAlchemy connection."""

    def __init__(self):
        pass

    def deployable_create(self, context, values):
        raise NotImplementedError() # TODO
        if not values.get('uuid'):
            values['uuid'] = uuidutils.generate_uuid()
        if values.get('id'):
            values.pop('id', None)
        deployable = models.Deployable()
        deployable.update(values)

        with _session_for_write() as session:
            try:
                session.add(deployable)
                session.flush()
            except db_exc.DBDuplicateEntry:
                raise exception.DeployableAlreadyExists(uuid=values['uuid'])
            return deployable

    def deployable_get(self, context, uuid):
        raise NotImplementedError() # TODO
        query = model_query(
            context,
            models.Deployable).filter_by(uuid=uuid)
        try:
            return query.one()
        except NoResultFound:
            raise exception.DeployableNotFound(uuid=uuid)

    def deployable_get_by_host(self, context, host):
        raise NotImplementedError() # TODO
        query = model_query(
            context,
            models.Deployable).filter_by(host=host)
        return query.all()

    def deployable_list(self, context):
        raise NotImplementedError() # TODO
        query = model_query(context, models.Deployable)
        return query.all()

    def deployable_update(self, context, uuid, values):
        raise NotImplementedError() # TODO
        if 'uuid' in values:
            msg = _("Cannot overwrite UUID for an existing Deployable.")
            raise exception.InvalidParameterValue(err=msg)

        try:
            return self._do_update_deployable(context, uuid, values)
        except db_exc.DBDuplicateEntry as e:
            if 'name' in e.columns:
                raise exception.DuplicateDeployableName(name=values['name'])

    @oslo_db_api.retry_on_deadlock
    def _do_update_deployable(self, context, uuid, values):
        with _session_for_write():
            query = model_query(context, models.Deployable)
            # query = add_identity_filter(query, uuid)
            query = query.filter_by(uuid=uuid)
            try:
                ref = query.with_lockmode('update').one()
            except NoResultFound:
                raise exception.DeployableNotFound(uuid=uuid)

            ref.update(values)
        return ref

    @oslo_db_api.retry_on_deadlock
    def deployable_delete(self, context, uuid):
        raise NotImplementedError() # TODO
        with _session_for_write():
            query = model_query(context, models.Deployable)
            query = add_identity_filter(query, uuid)
            query.update({'root_uuid': None})
            count = query.delete()
            if count != 1:
                raise exception.DeployableNotFound(uuid=uuid)

    def deployable_get_by_filters_with_attributes(self, context,
                                                  filters):
        raise NotImplementedError() # TODO

        exact_match_filter_names = ['uuid', 'name',
                                    'parent_uuid', 'root_uuid',
                                    'address', 'host',
                                    'board', 'vendor', 'version',
                                    'type', 'interface_type', 'assignable',
                                    'instance_uuid', 'availability',
                                    'accelerator_id']
        attribute_filters = {}
        filters_copy = copy.deepcopy(filters)
        for key, value in filters_copy.items():
            if key not in exact_match_filter_names:
                # This key is not in the deployable regular fields
                value = filters.pop(key)
                attribute_filters.update({key: value})

        query_prefix = model_query(context, models.Deployable)
        filters = copy.deepcopy(filters)

        # Filter the query
        query_prefix = self._exact_deployable_filter_with_attributes(
            query_prefix,
            filters,
            exact_match_filter_names,
            attribute_filters
            )
        if query_prefix is None:
            return []
        deployables = query_prefix.all()
        return deployables

    def deployable_get_by_filters(self, context,
                                  filters, sort_key='created_at',
                                  sort_dir='desc', limit=None,
                                  marker=None, join_columns=None):
        """Return list of deployables matching all filters sorted by
        the sort_key. See deployable_get_by_filters_sort for
        more information.
        """
        raise NotImplementedError() # TODO
        return self.deployable_get_by_filters_sort(context, filters,
                                                   limit=limit, marker=marker,
                                                   join_columns=join_columns,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir)

    def _exact_deployable_filter_with_attributes(self, query,
                                                 dpl_filters, legal_keys,
                                                 attribute_filters):
        """Applies exact match filtering to a deployable query.
        Returns the updated query.  Modifies dpl_filters argument to remove
        dpl_filters consumed.
        :param query: query to apply dpl_filters and attribute_filters to
        :param dpl_filters: dictionary of filters; values that are lists,
                        tuples, sets, or frozensets cause an 'IN' test to
                        be performed, while exact matching ('==' operator)
                        is used for other values
        :param legal_keys: list of keys to apply exact filtering to
        :param attribute_filters: dictionary of attribute filters
        """

        filter_dict = {}
        model = models.Deployable

        # Walk through all the keys
        for key in legal_keys:
            # Skip ones we're not filtering on
            if key not in dpl_filters:
                continue

            # OK, filtering on this key; what value do we search for?
            value = dpl_filters.pop(key)

            if isinstance(value, (list, tuple, set, frozenset)):
                if not value:
                    return None
                # Looking for values in a list; apply to query directly
                column_attr = getattr(model, key)
                query = query.filter(column_attr.in_(value))
            else:
                filter_dict[key] = value
        # Apply simple exact matches
        if filter_dict:
            query = query.filter(*[getattr(models.Deployable, k) == v
                                   for k, v in filter_dict.items()])
        if attribute_filters:
            query = query.outerjoin(models.Attribute)
            query = query.filter(or_(*[and_(models.Attribute.key == k,
                                 models.Attribute.value == v)
                                 for k, v in attribute_filters.items()]))
        return query

    def _exact_deployable_filter(self, query, filters, legal_keys):
        """Applies exact match filtering to a deployable query.
        Returns the updated query.  Modifies filters argument to remove
        filters consumed.
        :param query: query to apply filters to
        :param filters: dictionary of filters; values that are lists,
                        tuples, sets, or frozensets cause an 'IN' test to
                        be performed, while exact matching ('==' operator)
                        is used for other values
        :param legal_keys: list of keys to apply exact filtering to
        """

        filter_dict = {}
        model = models.Deployable

        # Walk through all the keys
        for key in legal_keys:
            # Skip ones we're not filtering on
            if key not in filters:
                continue

            # OK, filtering on this key; what value do we search for?
            value = filters.pop(key)

            if isinstance(value, (list, tuple, set, frozenset)):
                if not value:
                    return None
                # Looking for values in a list; apply to query directly
                column_attr = getattr(model, key)
                query = query.filter(column_attr.in_(value))
            else:
                filter_dict[key] = value
        # Apply simple exact matches
        if filter_dict:
            query = query.filter(*[getattr(models.Deployable, k) == v
                                   for k, v in filter_dict.items()])
        return query

    def deployable_get_by_filters_sort(self, context, filters, limit=None,
                                       marker=None, join_columns=None,
                                       sort_key=None, sort_dir=None):
        """Return deployables that match all filters sorted by the given
        keys. Deleted deployables will be returned by default, unless
        there's a filter that says otherwise.
        """
        raise NotImplementedError() # TODO

        if limit == 0:
            return []

        query_prefix = model_query(context, models.Deployable)
        filters = copy.deepcopy(filters)

        exact_match_filter_names = ['uuid', 'name',
                                    'parent_uuid', 'root_uuid',
                                    'address', 'host',
                                    'board', 'vendor', 'version',
                                    'type', 'interface_type', 'assignable',
                                    'instance_uuid', 'availability',
                                    'accelerator_id']

        # Filter the query
        query_prefix = self._exact_deployable_filter(query_prefix,
                                                     filters,
                                                     exact_match_filter_names)
        if query_prefix is None:
            return []
        return _paginate_query(context, models.Deployable, limit, marker,
                               sort_key, sort_dir, query_prefix)

    def attribute_create(self, context, values):
        raise NotImplementedError() # TODO
        if not values.get('uuid'):
            values['uuid'] = uuidutils.generate_uuid()
        if values.get('id'):
            values.pop('id', None)
        attribute = models.Attribute()
        attribute.update(values)

        with _session_for_write() as session:
            try:
                session.add(attribute)
                session.flush()
            except db_exc.DBDuplicateEntry:
                raise exception.AttributeAlreadyExists(
                    uuid=values['uuid'])
            return attribute

    def attribute_get(self, context, uuid):
        raise NotImplementedError() # TODO
        query = model_query(
            context,
            models.Attribute).filter_by(uuid=uuid)
        try:
            return query.one()
        except NoResultFound:
            raise exception.AttributeNotFound(uuid=uuid)

    def attribute_get_by_deployable_id(self, context, deployable_id):
        raise NotImplementedError() # TODO
        query = model_query(
            context,
            models.Attribute).filter_by(deployable_id=deployable_id)
        return query.all()

    def attribute_get_by_filter(self, context, filters):
        raise NotImplementedError() # TODO
        """Return attributes that matches the filters
        """
        query_prefix = model_query(context, models.Attribute)

        # Filter the query
        query_prefix = self._exact_attribute_by_filter(query_prefix,
                                                       filters)
        if query_prefix is None:
            return []

        return query_prefix.all()

    def _exact_attribute_by_filter(self, query, filters):
        """Applies exact match filtering to a atrtribute query.
        Returns the updated query.
        :param filters: The filters specified by a dict of kv pairs
        """

        model = models.Attribute
        filter_dict = filters

        # Apply simple exact matches
        query = query.filter(*[getattr(models.Attribute, k) == v
                               for k, v in filter_dict.items()])
        return query

    def attribute_update(self, context, uuid, key, value):
        raise NotImplementedError() # TODO
        return self._do_update_attribute(context, uuid, key, value)

    @oslo_db_api.retry_on_deadlock
    def _do_update_attribute(self, context, uuid, key, value):
        update_fields = {'key': key, 'value': value}
        with _session_for_write():
            query = model_query(context, models.Attribute)
            query = add_identity_filter(query, uuid)
            try:
                ref = query.with_lockmode('update').one()
            except NoResultFound:
                raise exception.AttributeNotFound(uuid=uuid)

            ref.update(update_fields)
        return ref

    def attribute_delete(self, context, uuid):
        raise NotImplementedError() # TODO
        with _session_for_write():
            query = model_query(context, models.Attribute)
            query = add_identity_filter(query, uuid)
            count = query.delete()
            if count != 1:
                raise exception.AttributeNotFound(uuid=uuid)

    def _get_quota_usages(self, context, project_id, resources=None):
        # Broken out for testability
        query = model_query(context, models.QuotaUsage,).filter_by(
            project_id=project_id)
        if resources:
            query = query.filter(models.QuotaUsage.resource.in_(
                list(resources)))
        rows = query.order_by(models.QuotaUsage.id.asc()). \
            with_for_update().all()
        return {row.resource: row for row in rows}

    def _quota_usage_create(self, project_id, resource, until_refresh,
                            in_use, reserved, session=None):

        quota_usage_ref = models.QuotaUsage()
        quota_usage_ref.project_id = project_id
        quota_usage_ref.resource = resource
        quota_usage_ref.in_use = in_use
        quota_usage_ref.reserved = reserved
        quota_usage_ref.until_refresh = until_refresh
        quota_usage_ref.save(session=session)

        return quota_usage_ref

    def _reservation_create(self, uuid, usage, project_id, resource, delta,
                            expire, session=None):
        usage_id = usage['id'] if usage else None
        reservation_ref = models.Reservation()
        reservation_ref.uuid = uuid
        reservation_ref.usage_id = usage_id
        reservation_ref.project_id = project_id
        reservation_ref.resource = resource
        reservation_ref.delta = delta
        reservation_ref.expire = expire
        reservation_ref.save(session=session)
        return reservation_ref

    def _get_reservation_resources(self, context, reservation_ids):
        """Return the relevant resources by reservations."""

        reservations = model_query(context, models.Reservation). \
            options(load_only('resource')). \
            filter(models.Reservation.uuid.in_(reservation_ids)). \
            all()
        return {r.resource for r in reservations}

    def _quota_reservations(self, session, context, reservations):
        """Return the relevant reservations."""

        # Get the listed reservations
        return model_query(context, models.Reservation). \
            filter(models.Reservation.uuid.in_(reservations)). \
            with_lockmode('update'). \
            all()

    def quota_reserve(self, context, resources, deltas, expire,
                      until_refresh, max_age, project_id=None,
                      is_allocated_reserve=False):
        """ Create reservation record in DB according to params"""
        with _session_for_write() as session:
            if project_id is None:
                project_id = context.project_id
            usages = self._get_quota_usages(context, project_id,
                                            resources=deltas.keys())
            work = set(deltas.keys())
            while work:
                resource = work.pop()

                # Do we need to refresh the usage?
                refresh = False
                # create quota usage in DB if there is no record of this type
                # of resource
                if resource not in usages:
                    usages[resource] = self._quota_usage_create(
                           project_id, resource, until_refresh or None,
                           in_use=0, reserved=0, session=session)
                    refresh = True
                elif usages[resource].in_use < 0:
                    # Negative in_use count indicates a desync, so try to
                    # heal from that...
                    refresh = True
                elif usages[resource].until_refresh is not None:
                    usages[resource].until_refresh -= 1
                    if usages[resource].until_refresh <= 0:
                        refresh = True
                elif max_age and usages[resource].updated_at is not None and (
                    (timeutils.utcnow() -
                        usages[resource].updated_at).total_seconds() >=
                        max_age):
                    refresh = True

                # refresh the usage
                if refresh:
                    # Grab the sync routine
                    updates= self._sync_acc_res(context, resource, project_id)
                    for res, in_use in updates.items():
                        # Make sure we have a destination for the usage!
                        if res not in usages:
                            usages[res] = self._quota_usage_create(
                                project_id,
                                res,
                                until_refresh or None,
                                in_use=0,
                                reserved=0,
                                session=session
                            )

                        # Update the usage
                        usages[res].in_use = in_use
                        usages[res].until_refresh = until_refresh or None

                        # Because more than one resource may be refreshed
                        # by the call to the sync routine, and we don't
                        # want to double-sync, we make sure all refreshed
                        # resources are dropped from the work set.
                        work.discard(res)

                        # NOTE(Vek): We make the assumption that the sync
                        #            routine actually refreshes the
                        #            resources that it is the sync routine
                        #            for.  We don't check, because this is
                        #            a best-effort mechanism.

            unders = [r for r, delta in deltas.items()
                      if delta < 0 and delta + usages[r].in_use < 0]
            reservations = []
            for resource, delta in deltas.items():
                usage = usages[resource]
                reservation = self._reservation_create(
                    str(uuid.uuid4()), usage, project_id, resource,
                    delta, expire, session=session)
                reservations.append(reservation.uuid)
                usages[resource].reserved += delta
            session.flush()
        if unders:
            LOG.warning("Change will make usage less than 0 for the "
                        "following resources: %s", unders)
        return reservations

    def _sync_acc_res(self, context, resource, project_id):
        """Quota sync funciton"""
        res_in_use = self._accelerator_data_get_for_project(context, resource,
                                                            project_id)
        return {resource: res_in_use}

    def _accelerator_data_get_for_project(self, context, resource,project_id):
        """Return the number of resource which is being used by a project"""
        raise NotImplementedError()
        query = model_query(context, models.Accelerator).\
            filter_by(project_id=project_id).filter_by(device_type=resource)

        return query.count()

    def _dict_with_usage_id(self, usages):
        return {row.id: row for row in usages.values()}

    def reservation_commit(self, context, reservations, project_id=None):
        """Commit quota reservation to quota usage table"""
        with _session_for_write() as session:
            quota_usage = self._get_quota_usages(
                context, project_id,
                resources=self._get_reservation_resources(context,
                                                          reservations))
            usages = self._dict_with_usage_id(quota_usage)

            for reservation in self._quota_reservations(session, context,
                                                        reservations):

                usage = usages[reservation.usage_id]
                if reservation.delta >= 0:
                    usage.reserved -= reservation.delta
                usage.in_use += reservation.delta
                session.flush()
                reservation.delete(session=session)

    def process_sort_params(self, sort_keys, sort_dirs,
                            default_keys=['created_at', 'id'],
                            default_dir='asc'):

        # Determine direction to use for when adding default keys
        if sort_dirs and len(sort_dirs) != 0:
            default_dir_value = sort_dirs[0]
        else:
            default_dir_value = default_dir

        # Create list of keys (do not modify the input list)
        if sort_keys:
            result_keys = list(sort_keys)
        else:
            result_keys = []

        # If a list of directions is not provided,
        # use the default sort direction for all provided keys
        if sort_dirs:
            result_dirs = []
            # Verify sort direction
            for sort_dir in sort_dirs:
                if sort_dir not in ('asc', 'desc'):
                    msg = _("Unknown sort direction, must be 'desc' or 'asc'")
                    raise exception.InvalidInput(reason=msg)
                result_dirs.append(sort_dir)
        else:
            result_dirs = [default_dir_value for _sort_key in result_keys]

        # Ensure that the key and direction length match
        while len(result_dirs) < len(result_keys):
            result_dirs.append(default_dir_value)
        # Unless more direction are specified, which is an error
        if len(result_dirs) > len(result_keys):
            msg = _("Sort direction size exceeds sort key size")
            raise exception.InvalidInput(reason=msg)

        # Ensure defaults are included
        for key in default_keys:
            if key not in result_keys:
                result_keys.append(key)
                result_dirs.append(default_dir_value)

        return result_keys, result_dirs

    def device_profile_create(self, context, values):
        if not values.get('uuid'):
            values['uuid'] = uuidutils.generate_uuid()

        devprof = models.DeviceProfile()
        devprof.update(values)

        with _session_for_write() as session:
            try:
                session.add(devprof)
                session.flush()
            except db_exc.DBDuplicateEntry:
                raise RuntimeError() # TODO use specific exception
            return devprof

    def device_profile_get(self, context, name):
        query = model_query(context,
                   models.DeviceProfile).filter_by(name=name)
        try:
            return query.one()
        except NoResultFound:
            raise RuntimeError() # TODO use specific exception

    def device_profile_get_by_id(self, context, id):
        query = model_query(context,
                   models.DeviceProfile).filter_by(id=id)
        try:
            return query.one()
        except NoResultFound:
            raise RuntimeError('No device profile with id (%s)' % id)

    def device_profile_list(self, context):
        query = model_query(context, models.DeviceProfile)
        return query.all()

    def device_profile_update(self, context, name, values):
        try:
            return self._do_update_device_profile(context, name, values)
        except db_exc.DBDuplicateEntry as e:
            raise RuntimeError() # TODO use specific exception

    @oslo_db_api.retry_on_deadlock
    def _do_update_device_profile(self, context, name, values):
        with _session_for_write():
            query = model_query(context, models.DeviceProfile)
            query = add_identity_filter(query, name)
            try:
                ref = query.with_lockmode('update').one()
            except NoResultFound:
                raise RuntimeError() # TODO use specific exception

            ref.update(values)
        return ref

    def device_profile_delete(self, context, name):
        with _session_for_write():
            query = model_query(context, models.DeviceProfile)
            query = add_identity_filter(query, name)
            count = query.delete()
            if count != 1:
                raise RuntimeError() # TODO use specific exception

    def extarq_create(self, context, values):
        if not values.get('uuid'):
            values['uuid'] = uuidutils.generate_uuid()

        if values.get('device_profile_id'):
            pass # Already have the devprof id, so nothing to do
        elif values.get('device_profile_name'):
            MYLOG.warning("db extarq_create: Querying devprof to get id.")
            devprof = self.device_profile_get(context,
                                  values['device_profile_name'])
            values['device_profile_id'] = devprof['id']
        else:
            raise RuntimeError('Device profile name/id required')

        extarq = models.ExtARQ()
        extarq.update(values)

        with _session_for_write() as session:
            try:
                session.add(extarq)
                session.flush()
            except db_exc.DBDuplicateEntry:
                raise RuntimeError('Duplicate ExtARQ')
            return extarq

    def extarq_get(self, context, uuid):
        query = model_query(context,
                   models.ExtARQ).filter_by(uuid=uuid)
        try:
            return query.one()
        except NoResultFound:
            raise RuntimeError('No ExtARQ found with UUID %s' % uuid)

    def extarq_list(self, context):
        query = model_query(context, models.ExtARQ)
        return query.all()

    def extarq_update(self, context, uuid, values):
        try:
            return self._do_update_extarq(context, uuid, values)
        except db_exc.DBDuplicateEntry as e:
            raise RuntimeError() # TODO use specific exception

    @oslo_db_api.retry_on_deadlock
    def _do_update_extarq(self, context, uuid, values):
        with _session_for_write():
            query = model_query(context, models.ExtARQ)
            query = add_identity_filter(query, uuid)
            try:
                ref = query.with_lockmode('update').one()
            except NoResultFound:
                raise RuntimeError() # TODO use specific exception

            ref.update(values)
        return ref

    def extarq_delete(self, context, uuid):
        with _session_for_write():
            query = model_query(context, models.ExtARQ)
            query = add_identity_filter(query, uuid)
            count = query.delete()
            if count != 1:
                raise RuntimeError() # TODO use specific exception
