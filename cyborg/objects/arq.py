# Copyright 2018 Huawei Technologies Co.,LTD.
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

from oslo_log import log as logging
from oslo_versionedobjects import base as object_base

from cyborg.common import exception
from cyborg.db import api as dbapi
from cyborg.objects import base
from cyborg.objects import fields as object_fields
from cyborg.objects.attribute import Attribute

LOG = logging.getLogger(__name__)
MYLOG=LOG

@base.CyborgObjectRegistry.register
class ARQ(base.CyborgObject, object_base.VersionedObjectDictCompat):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = dbapi.get_instance()

    fields = {
        'id': object_fields.IntegerField(nullable=False),
        'uuid': object_fields.UUIDField(nullable=False),
        'state': object_fields.StringField(nullable=False),
        'device_profile_name': object_fields.StringField(nullable=False),
        'host_name': object_fields.StringField(),
        'device_rp_uuid': object_fields.StringField(), # TODO uuidfield?
        'instance_uuid': object_fields.StringField(), # TODO uuidfield?
    }

    def create(self, context, device_profile_id=None):
        """Create an ARQ record in the DB."""
        # HACK TODO validate properly
        if 'device_profile_name' not in self:
            raise exception.ObjectActionError(action='create',
                      reason='device profile name is required')

        # db layer will create an UUID if needed
        self.state = 'Initial'

        values = self.obj_get_changes()

        # Pass devprof id to db layer, to avoid repeated queries
        if device_profile_id is not None:
            values['device_profile_id'] = device_profile_id

        db_arq = self.dbapi.arq_create(context, values)
        for n in ['host_name', 'device_rp_uuid', 'instance_uuid']:
            # HACK: force these fields to be not None
            if db_arq[n] is None:
                db_arq[n] = ''
        self._from_db_object(self, db_arq)

    @classmethod
    def get(cls, context, uuid):
        """Find a DB ARQ and return an Obj ARQ."""
        db_arq = cls.dbapi.arq_get(context, uuid)
        db_devprof = cls.dbapi.device_profile_get_by_id(context,
                         db_arq.device_profile_id)
        db_arq['device_profile_name'] = db_devprof['name']
        for n in ['host_name', 'device_rp_uuid', 'instance_uuid']:
            # HACK: force these fields to be not None
            #    This should probably be in db layer
            if db_arq[n] is None:
                db_arq[n] = ''
        MYLOG.warning('obj arq get: db_arq: (%s), dpname: (%s)',
                      db_arq, db_arq['device_profile_name'])
        obj_arq = cls._from_db_object(cls(context), db_arq)
        return obj_arq

    @classmethod
    def list(cls, context):
        """Return a list of ARQ objects."""
        db_arqs = cls.dbapi.arq_list(context)
        for db_arq in db_arqs:
           db_devprof = cls.dbapi.device_profile_get_by_id(context,
                            db_arq.device_profile_id)
           db_arq['device_profile_name'] = db_devprof['name']
           # HACK: force these fields to be not None
           for n in ['host_name', 'device_rp_uuid', 'instance_uuid']:
               if db_arq[n] is None:
                   db_arq[n] = ''
        obj_dp_list = cls._from_db_object_list(db_arqs, context)
        return obj_dp_list

    def save(self, context):
        """Update an ARQ record in the DB."""
        updates = self.obj_get_changes()
        db_arq = self.dbapi.arq_update(context, self.uuid, updates)
        db_devprof = ARQ.dbapi.device_profile_get_by_id(context,
                            db_arq.device_profile_id)
        db_arq['device_profile_name'] = db_devprof['name']
        self._from_db_object(self, db_arq)

    def destroy(self, context):
        """Delete an ARQ from the DB."""
        self.dbapi.arq_delete(context, self.name)
        self.obj_reset_changes()

    @classmethod
    def _from_db_object(cls, arq, db_arq):
        """Converts an ARQ to a formal object.

        :param arq: An object of the class ARQ
        :param db_arq: A DB model of the object
        :return: The object of the class with the database entity added
        """
        arq = base.CyborgObject._from_db_object(arq, db_arq)
        return arq
