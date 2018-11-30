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
class ExtARQ(base.CyborgObject, object_base.VersionedObjectDictCompat):
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

         # TODO Shd be attach_handle object, with PCI subclass
        'attach_handle_id_pci': object_fields.StringField()
    }

    def create(self, context, device_profile_id=None):
        """Create an ExtARQ record in the DB."""
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

        db_extarq = self.dbapi.extarq_create(context, values)
        for n in ['host_name', 'device_rp_uuid', 'instance_uuid']:
            # HACK: force these fields to be not None
            if db_extarq[n] is None:
                db_extarq[n] = ''
        self._from_db_object(self, db_extarq)

    @classmethod
    def get(cls, context, uuid):
        """Find a DB ExtARQ and return an Obj ExtARQ."""
        db_extarq = cls.dbapi.extarq_get(context, uuid)
        db_devprof = cls.dbapi.device_profile_get_by_id(context,
                         db_extarq.device_profile_id)
        db_extarq['device_profile_name'] = db_devprof['name']
        for n in ['host_name', 'device_rp_uuid', 'instance_uuid']:
            # HACK: force these fields to be not None
            #    This should probably be in db layer
            if db_extarq[n] is None:
                db_extarq[n] = ''
        MYLOG.warning('obj extarq get: db_extarq: (%s), dpname: (%s)',
                      db_extarq, db_extarq['device_profile_name'])
        obj_extarq = cls._from_db_object(cls(context), db_extarq)
        return obj_extarq

    @classmethod
    def list(cls, context):
        """Return a list of ExtARQ objects."""
        db_extarqs = cls.dbapi.extarq_list(context)
        for db_extarq in db_extarqs:
           db_devprof = cls.dbapi.device_profile_get_by_id(context,
                            db_extarq.device_profile_id)
           db_extarq['device_profile_name'] = db_devprof['name']
           # HACK: force these fields to be not None
           for n in ['host_name', 'device_rp_uuid', 'instance_uuid']:
               if db_extarq[n] is None:
                   db_extarq[n] = ''
        obj_dp_list = cls._from_db_object_list(db_extarqs, context)
        return obj_dp_list

    def save(self, context):
        """Update an ExtARQ record in the DB."""
        updates = self.obj_get_changes()
        db_extarq = self.dbapi.extarq_update(context, self.uuid, updates)
        db_devprof = ExtARQ.dbapi.device_profile_get_by_id(context,
                            db_extarq.device_profile_id)
        db_extarq['device_profile_name'] = db_devprof['name']
        self._from_db_object(self, db_extarq)

    def destroy(self, context):
        """Delete an ExtARQ from the DB."""
        self.dbapi.extarq_delete(context, self.name)
        self.obj_reset_changes()

    # HACK: all binding logic should be in the conductor
    def bind(self, context, device_rp_uuid):
        """ Given a device rp UUID, get the deployable UUID and
            an attach handle.
        """
        # HACK: hardcode values for now.
        attach_handle_id_pci = "0000:00.5e.0"

    @classmethod
    def _from_db_object(cls, extarq, db_extarq):
        """Converts an ExtARQ to a formal object.

        :param extarq: An object of the class ExtARQ
        :param db_extarq: A DB model of the object
        :return: The object of the class with the database entity added
        """
        extarq = base.CyborgObject._from_db_object(extarq, db_extarq)
        return extarq
