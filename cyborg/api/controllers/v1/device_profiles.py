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
from oslo_serialization import jsonutils

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

LOG = log.getLogger(__name__)
MYLOG = LOG

class DeviceProfile(base.APIBase):
    """API representation of a device profile.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation of
    a device profile.
    """
    uuid = wtypes.text # types.uuid
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

class DeviceProfilesController(base.CyborgController):
    """REST controller for DeviceProfiles."""

    # @policy.authorize_wsgi("cyborg:device_profile", "create", False)
    @expose.expose(DeviceProfile, body=types.jsontype,
                   status_code=http_client.CREATED)
    def post(self, devprof):
        """Create a new device_profile.

        :param devprof: a device_profile within the request body.
        HACK Support more than one devprof per request
        """
        context = pecan.request.context
        obj_devprof = objects.DeviceProfile(context, **devprof)
        new_devprof = pecan.request.conductor_api.device_profile_create(context,
                                                                obj_devprof)
        # Set the HTTP Location Header
        pecan.response.location = link.build_url('device_profiles',
                                                 new_devprof.uuid)
        return DeviceProfile.convert_with_links(new_devprof)

    # @policy.authorize_wsgi("cyborg:device_profile", "get_all")
    @expose.expose(DeviceProfileCollection, wtypes.text, wtypes.text)
    def get_all(self, name='None', use='None'):
        """Retrieve a list of device_profiles."""
        name = pecan.request.GET.get('name')
        use  = pecan.request.GET.get('use')

        context = pecan.request.context
        obj_devprofs = objects.DeviceProfile.list(context)
        if name:
            new_obj_devprofs = [devprof for devprof in obj_devprofs
                                 if devprof['name'] in name]
            obj_devprofs = new_obj_devprofs
        if use is not None and use == 'scheduling':
            # TODO Figure out how to support this
            # Returning just the devprof groups causes Pecan issues
            pass
        # HACK fix convert_links
        return DeviceProfileCollection.convert_with_links(obj_devprofs)
        #return obj_devprofs

    # @policy.authorize_wsgi("cyborg:device_profile", "delete")
    @expose.expose(DeviceProfile, wtypes.text, status_code=http_client.NO_CONTENT)
    def delete(self, name):
        """Delete a device_profile.

        :param name: name of a device_profile.
        HACK Support more than one devprof per request
        """
        context = pecan.request.context
        obj_devprof = objects.DeviceProfile.get(context, name)
        # TODO Implement device profile delete
        pecan.request.conductor_api.device_profile_delete(context,
                              obj_devprof)
