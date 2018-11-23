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

@base.CyborgObjectRegistry.register
class DeviceProfile(base.CyborgObject, object_base.VersionedObjectDictCompat):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = dbapi.get_instance()

    fields = {
        'id': object_fields.IntegerField(nullable=False),
        'uuid': object_fields.UUIDField(nullable=False),
        'name': object_fields.StringField(nullable=False),
        'json': object_fields.StringField(nullable=False),
    }

    def create(self, context):
        """Create a Device Profile record in the DB."""
        # HACK validate with a JSON schema
        if 'name' not in self:
            raise exception.ObjectActionError(action='create',
                                              reason='name is required')

        values = self.obj_get_changes()

        db_devprof = self.dbapi.device_profile_create(context, values)
        self._from_db_object(self, db_devprof)

    @classmethod
    def get(cls, context, name):
        """Find a DB Device Profile and return an Obj Device Profile."""
        db_devprof = cls.dbapi.device_profile_get(context, name)
        obj_devprof = cls._from_db_object(cls(context), db_devprof)
        return obj_devprof

    @classmethod
    def list(cls, context):
        """Return a list of Device Profile objects."""
        db_devprofs = cls.dbapi.device_profile_list(context)
        obj_dp_list = cls._from_db_object_list(db_devprofs, context)
        return obj_dp_list

    def save(self, context):
        """Update a Device Profile record in the DB."""
        updates = self.obj_get_changes()
        db_devprof = self.dbapi.device_profile_update(context, self.uuid, updates)
        self._from_db_object(self, db_devprof)

    def destroy(self, context):
        """Delete a Device Profile from the DB."""
        self.dbapi.device_profile_delete(context, self.name)
        self.obj_reset_changes()

    @classmethod
    def _from_db_object(cls, obj, db_obj):
        """Converts a device_profile to a formal object.

        :param obj: An object of the class.
        :param db_obj: A DB model of the object
        :return: The object of the class with the database entity added
        """
        obj = base.CyborgObject._from_db_object(obj, db_obj)

        return obj
