============================
Cyborg Nova Proof of Concept
============================

This is a Proof of Concept (POC) for OpenStack developer community to see how
Cyborg will interact with Nova. It includes changes to upstream Cyborg
and Nova.

The POC is intended to show the representation of devices in Placement, API
signatures and calls, device prifle structure and the rough device model as
reflected in Cyborg db schema. It is *not* intended to show the Cyborg
implementation details, many of which are only simulated in the POC.

POC vs Eventual Implementation
==============================

* The accelerator devices need to be discovered and represented in Placement.
  Eventually, Cyborg will discover devices via Cyborg drivers, represent them
  in its db and call Placement. But, in the POC, this is simulated by running
  ``nova_integ/initial_setup.sh``: there are no real devices or drivers, only
  entries in Cyborg db and Placement/nova-api db, modeling a single device.
 
* Device profiles can be created using Cyborg APIs, same as in real world. 



Cyborg References
=================
* Free software: Apache license
* Source: https://git.openstack.org/cgit/openstack/cyborg
* Bugs: https://bugs.launchpad.net/openstack-cyborg
* Blueprints: https://blueprints.launchpad.net/openstack-cyborg

