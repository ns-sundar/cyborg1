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

"""Version 2 of the Cyborg API"""

import pecan
from pecan import rest
from wsme import types as wtypes

from cyborg.api.controllers import base
from cyborg.api.controllers import link
from cyborg.api.controllers.v2 import accelerators
from cyborg.api.controllers.v2 import deployables
from cyborg.api.controllers.v2 import device_profiles
from cyborg.api.controllers.v2 import arqs
from cyborg.api.controllers.v2 import arq_bindings
from cyborg.api import expose


class V1(base.APIBase):
    """The representation of the version 1 of the API."""

    id = wtypes.text
    """The ID of the version"""

    accelerator = [link.Link]
    """Links to the accelerator resource"""

    @staticmethod
    def convert():
        v2 = V1()
        v2.id = 'v2'
        v2.accelerator = [
            link.Link.make_link('self', pecan.request.public_url,
                                'accelerator', ''),
            link.Link.make_link('bookmark', pecan.request.public_url,
                                'accelerator', '', bookmark=True)
            ]
        return v2


class Controller(rest.RestController):
    """Version 1 API controller root"""

    accelerators = accelerators.AcceleratorsController()
    deployables = deployables.DeployablesController()
    device_profiles = device_profiles.DeviceProfilesController()
    arqs = arqs.ARQsController()
    arq_bindings = arq_bindings.ARQBindingsController()

    @expose.expose(V1)
    def get(self):
        return V1.convert()


__all__ = ('Controller',)
