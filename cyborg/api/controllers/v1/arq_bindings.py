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

class ARQBinding(base.APIBase):
    """API representation of an ARQBinding.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation.
    """
    uuid = types.uuid
    """UUID of the ARQ for this binding"""

    host_name = wtypes.text
    """Host name to be bound"""

    device_rp_uuid = wtypes.text
    """UUID of the device RP to be bound"""

    instance_uuid = wtypes.text
    """UUID of the instance  to be bound"""

    def __init__(self, **kwargs):
        super(ARQBinding, self).__init__(**kwargs)
        self.fields = []
        for field in objects.ARQBinding.fields:
            self.fields.append(field)
            setattr(self, field, kwargs.get(field, wtypes.Unset))

    @classmethod
    def convert_with_links(cls, obj_binding):
        api_binding = cls(**obj_binding.as_dict())
        url = pecan.request.public_url
        api_binding.links = [] # No API URL for ARQBinding
        return api_binding

class ARQBindingCollection(base.APIBase):
    """API representation of a collection of bindings."""

    bindings = [ARQBinding]
    """A list containing binding objects"""

    @classmethod
    def convert_with_links(cls, obj_bindings):
        collection = cls()
        collection.bindings = [ARQBinding.convert_with_links(obj_binding)
                                  for obj_binding in obj_bindings]
        return collection

class ARQBindingsController(base.CyborgController):
    """REST controller for ARQBindings."""

    # @policy.authorize_wsgi("cyborg:binding", "create", False)
    @expose.expose(ARQBinding, body=types.jsontype,
                   status_code=http_client.ACCEPTED)
    def post(self, req):
        """Create new bindings.
           Request body:
           { "bindings":
             [
               { "arq_uuid": <uuid>,
                 "host_name": <string>,
                 "device_rp_uuid": <uuid>,
                 "instance_uuid": <uuid>
               }
             ]
           }
           :param req: request body.
        """

        def _validate_params(req):
            arq_uuid = req.get('arq_uuid')
            if arq_uuid is None:
               raise RuntimeError('Binding needs ARQ UUID')
            host_name = req.get('host_name')
            if host_name is None:
               raise RuntimeError('Binding needs host name')
            devrp_uuid = req.get('device_rp_uuid')
            if devrp_uuid is None:
               raise RuntimeError('Binding needs device RP UUID')
            instance_uuid = req.get('instance_uuid')
            if instance_uuid is None:
               raise RuntimeError('Binding needs instance uUID')
            return arq_uuid, host_name, devrp_uuid, instance_uuid
            
        # HACK assume only one ARQBinding per request for now
        reqlist = req['bindings']
        if len(reqlist) > 1:
           raise RuntimeError('Only 1 binding per request for now')
        req = reqlist[0]

        arq_uuid, host_name, devrp_uuid, instance_uuid = _validate_params(req)

        context = pecan.request.context
        arq = objects.ARQ.get(context, arq_uuid)
        arq['host_name'] = host_name
        arq['device_rp_uuid'] = devrp_uuid
        arq['instance_uuid'] = instance_uuid

        # HACK We should call Cyborg agent/driver to do the actual
        # binding. Instead, we cheat by picking a VF and setting the
        # state. TODO Pick a VF
        arq['state'] = 'Bound'
        MYLOG.warning('ctrlr post bind: arq=(%s)', arq)

        arq.save(context) # HACK Delegate db writes to the conductor

        return None

    # @policy.authorize_wsgi("cyborg:binding", "delete")
    @expose.expose(None, wtypes.text, status_code=http_client.NO_CONTENT)
    def delete(self, arqs):
        """Delete a binding.

        :param arqs: List of ARQ UUIDs
        """
        MYLOG.warning('ctrlr DEL bind: env=(%s)', pecan.request.environ)
        got = pecan.request.GET.get('arqs')
        MYLOG.warning('ctrlr DEL bind: got=(%s) arqs=(%s)', got, arqs)
        if arqs is not None:
           uuid = arqs # HACK Assume only 1 binding for now
        else:
           raise RuntimeError('Delete ARQ bind needs at least one ARQ UUID')

        context = pecan.request.context
        arq = objects.ARQ.get(context, uuid)

        arq['host_name'] = ''
        arq['device_rp_uuid'] = ''
        # Retain instance_uuid in ARQ for troubleshooting
        arq['state'] = 'Unbound' # HACK Shd go back to what Nova set it to

        arq.save(context) # HACK Delegate db writes to the conductor
