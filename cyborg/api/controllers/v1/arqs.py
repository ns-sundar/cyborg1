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

class ARQ(base.APIBase):
    """API representation of an ARQ.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation.
    """
    uuid = types.uuid
    """The UUID of the device profile"""

    state = wtypes.text # obvious meanings
    device_profile_name = wtypes.text

    host_name = wtypes.text
    """The host name to which the ARQ is bound, if any"""

    device_rp_uuid = wtypes.text
    """The UUID of the bound device RP, if any"""

    instance_uuid = wtypes.text
    """The UUID of the instance associated with this ARQ, if any"""

    links = wsme.wsattr([link.Link], readonly=True)
    """A list containing a self link"""

    def __init__(self, **kwargs):
        super(ARQ, self).__init__(**kwargs)
        self.fields = []
        for field in objects.ARQ.fields:
            self.fields.append(field)
            setattr(self, field, kwargs.get(field, wtypes.Unset))

    @classmethod
    def convert_with_links(cls, obj_arq):
        api_arq = cls(**obj_arq.as_dict())
        url = pecan.request.public_url
        api_arq.links = [] # HACK Links refer to UUID
        """
        api_arq.links = [
            link.Link.make_link('self', url, 'arqs', api_arq.uuid),
            link.Link.make_link('bookmark', url, 'arqs', api_arq.uuid,
                                bookmark=True)
            ]
        """
        return api_arq

class ARQCollection(base.APIBase):
    """API representation of a collection of arqs."""

    arqs = [ARQ]
    """A list containing arq objects"""

    @classmethod
    def convert_with_links(cls, obj_arqs):
        collection = cls()
        collection.arqs = [ARQ.convert_with_links(obj_arq)
                                  for obj_arq in obj_arqs]
        return collection

class ARQsController(base.CyborgController):
    """REST controller for ARQs."""

    def _get_devprof_id(self, context, devprof_name):
        """ Get the contents of a device profile.
            Since this is just a read, it is ok for the API layer
            to do this, instead of the conductor.
        """
        try:
           obj_devprof = objects.DeviceProfile.get(context, devprof_name)
           return obj_devprof['id']
        except:
           return None

    # @policy.authorize_wsgi("cyborg:arq", "create", False)
    @expose.expose(ARQ, body=types.jsontype,
                   status_code=http_client.CREATED)
    def post(self, req):
        """Create a new arq.
           Request body:
              { 'device_profile_name': <string>, # required
                'image_uuid': <glance-image-UUID>, #optional
              }
           :param req: request body.
        """
        # HACK assume only one ARQ per dev prof for now
        # HACK ignore image_uuid for now
        context = pecan.request.context
        obj_arq = objects.ARQ(context, **req)

        # Get devprof details and set devprof ID in arq.
        # This allows the conductor and db layer to skip the devprof query.
        devprof_id = None
        if req.get('device_profile_name'):
           devprof_id = self._get_devprof_id(
                                 context, req['device_profile_name'])
           if devprof_id is None:
              raise RuntimeError('Device profile not found')
        else:
           raise RuntimeError('No devprof name') # HACK use specific exception

        new_arq = pecan.request.conductor_api.arq_create(context,
                                              obj_arq, devprof_id)
        # Set the HTTP Location Header
        pecan.response.location = link.build_url('arqs', new_arq.uuid)
        return ARQ.convert_with_links(new_arq)

    # @policy.authorize_wsgi("cyborg:arq", "get_all")
    @expose.expose(ARQCollection, wtypes.text, types.uuid)
    def get_all(self, state=None, instance=None):
        """Retrieve a list of arqs."""
        # HACK Need to implement 'arq=uuid1,...' query parameter
        context = pecan.request.context
        obj_arqs = objects.ARQ.list(context)
        if state is not None:
            if state != 'resolved':
                raise RuntimeError('Only state "resolved" is supported')
            new_arqs = [arq for arq in obj_arqs
                           if arq['state'] == 'Bound' or
                              arq['state'] == 'BindFailed'
                       ]
            obj_arqs = new_arqs
        if instance is not None:
            new_arqs = [arq for arq in obj_arqs
                           if arq['instance_uuid'] == instance
                       ]
            obj_arqs = new_arqs

        return ARQCollection.convert_with_links(obj_arqs)

    # @policy.authorize_wsgi("cyborg:arq", "delete")
    @expose.expose(None, wtypes.text, status_code=http_client.NO_CONTENT)
    def delete(self, arqlist=None):
        """Delete a arq.

        :param arqlist: List of ARQ UUIDs
        """
        if arqlist is not None:
           uuid = arqlist[0] # HACK
        context = pecan.request.context
        obj_arq = objects.ARQ.get(context, uuid)
        pecan.request.conductor_api.arq_delete(context, obj_arq)
