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

import json
import pecan
from six.moves import http_client
import wsme
from wsme import types as wtypes

from oslo_log import log

from cyborg.api.controllers import base
from cyborg.api.controllers import link
from cyborg.api.controllers.v1 import types
from cyborg.api.controllers.v1 import utils as api_utils
from cyborg.api import expose
from cyborg.common import exception
from cyborg.common import policy
from cyborg import objects
from cyborg.quota import QUOTAS
from cyborg.agent.rpcapi import AgentAPI

class DeviceProfile(base.APIBase):
    """API representation of a device profile.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation of
    a device profile.
    """
    uuid = types.uuid
    """The UUID of the device profile"""

    name = wtypes.text
    """The name of the device profile"""

    json = types.jsontype
    """The JSON content of the device profile"""

    links = wsme.wsattr([link.Link], readonly=True)
    """A list containing a self link"""

    def __init__(self, **kwargs):
        super(DeviceProfile, self).__init__(**kwargs)
        self.fields = []
        for field in objects.DeviceProfile.fields:
            self.fields.append(field)
            setattr(self, field, kwargs.get(field, wtypes.Unset))

    @classmethod
    def convert_with_links(cls, obj_devprof):
        api_devprof = cls(**obj_devprof.as_dict())
        url = pecan.request.public_url
        api_devprof.links = [
            link.Link.make_link('self', url, 'device_profiles', api_devprof.uuid),
            link.Link.make_link('bookmark', url, 'device_profiles', api_devprof.uuid,
                                bookmark=True)
            ]
        # TODO query = {"device_profile_id": obj_devprof.id}
        return api_devprof


class DeviceProfileCollection(base.APIBase):
    """API representation of a collection of device_profiles."""

    device_profiles = [DeviceProfile]
    """A list containing device_profile objects"""

    @classmethod
    def convert_with_links(cls, obj_devprofs):
        collection = cls()
        collection.device_profiles = [DeviceProfile.convert_with_links(obj_devprof)
                                  for obj_devprof in obj_devprofs]
        return collection


class DeviceProfilePatchType(types.JsonPatchType):

    _api_base = DeviceProfile

    @staticmethod
    def internal_attrs():
        defaults = types.JsonPatchType.internal_attrs()
        return defaults + ['/address', '/host', '/type']


class DeviceProfilesController(base.CyborgController):
    """REST controller for DeviceProfiles."""

    _custom_actions = {'program': ['PATCH']}

    # @policy.authorize_wsgi("cyborg:device_profile", "create", False)
    @expose.expose(DeviceProfile, body=types.jsontype,
                   status_code=http_client.CREATED)
    def post(self, devprof):
        """Create a new device_profile.

        :param devprof: a device_profile within the request body.
        """
        context = pecan.request.context
        obj_devprof = objects.DeviceProfile(context, **devprof)
        new_devprof = pecan.request.conductor_api.device_profile_create(context,
                                                                obj_devprof)
        # Set the HTTP Location Header
        pecan.response.location = link.build_url('device_profiles', new_devprof.uuid)
        return DeviceProfile.convert_with_links(new_devprof)

    # @policy.authorize_wsgi("cyborg:device_profile", "get_one")
    @expose.expose(DeviceProfile, types.uuid)
    def get_one(self, uuid):
        """Retrieve information about the given device_profile.

        :param uuid: UUID of a device_profile.
        """
        obj_devprof = objects.DeviceProfile.get(pecan.request.context, uuid)
        return DeviceProfile.convert_with_links(obj_devprof)

    # @policy.authorize_wsgi("cyborg:device_profile", "get_all")
    @expose.expose(DeviceProfileCollection, int, types.uuid, wtypes.text,
                   wtypes.text, wtypes.ArrayType(types.FilterType))
    # TODO(wangzhh): Remove limit, marker, sort_key, sort_dir in next release.
    # They are used to compatible with R release client.
    def get_all(self, limit=None, marker=None, sort_key='id', sort_dir='asc',
                filters=None):
        """Retrieve a list of device_profiles."""
        filters_dict = {}
        self._generate_filters(limit, sort_key, sort_dir, filters_dict)
        if filters:
            for filter in filters:
                filters_dict.update(filter.as_dict())
        context = pecan.request.context
        if marker:
            marker_obj = objects.DeviceProfile.get(context, marker)
            filters_dict["marker_obj"] = marker_obj
        obj_devprofs = objects.DeviceProfile.list(context)
        return DeviceProfileCollection.convert_with_links(obj_devprofs)

    def _generate_filters(self, limit, sort_key, sort_dir, filters_dict):
        """This method are used to compatible with R release client."""
        if limit:
            filters_dict["limit"] = limit
        if sort_key:
            filters_dict["sort_key"] = sort_key
        if sort_dir:
            filters_dict["sort_dir"] = sort_dir

    # @policy.authorize_wsgi("cyborg:device_profile", "delete")
    @expose.expose(None, types.uuid, status_code=http_client.NO_CONTENT)
    def delete(self, uuid):
        """Delete a device_profile.

        :param uuid: UUID of a device_profile.
        """
        context = pecan.request.context
        obj_devprof = objects.DeviceProfile.get(context, uuid)
        pecan.request.conductor_api.device_profile_delete(context, obj_devprof)
