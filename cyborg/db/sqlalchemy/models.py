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

"""SQLAlchemy models for accelerator service."""

from oslo_db import options as db_options
from oslo_db.sqlalchemy import models
from oslo_utils import timeutils
import six.moves.urllib.parse as urlparse
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Index
from sqlalchemy import Text
from sqlalchemy import schema
from sqlalchemy import DateTime
from sqlalchemy import orm

from cyborg.common import paths
from cyborg.conf import CONF


_DEFAULT_SQL_CONNECTION = 'sqlite:///' + paths.state_path_def('cyborg.sqlite')
db_options.set_defaults(CONF, connection=_DEFAULT_SQL_CONNECTION)


def table_args():
    engine_name = urlparse.urlparse(CONF.database.connection).scheme
    if engine_name == 'mysql':
        return {'mysql_engine': CONF.database.mysql_engine,
                'mysql_charset': "utf8"}
    return None


class CyborgBase(models.TimestampMixin, models.ModelBase):
    metadata = None

    def as_dict(self):
        d = {}
        for c in self.__table__.columns:
            d[c.name] = self[c.name]
        return d

    @staticmethod
    def delete_values():
        return {'deleted': True,
                'deleted_at': timeutils.utcnow()}

    def delete(self, session):
        """Delete this object."""
        updated_values = self.delete_values()
        self.update(updated_values)
        self.save(session=session)
        return updated_values


Base = declarative_base(cls=CyborgBase)

class Device(Base):
    """Represents physical hardware, such as a PCI card.
       It contains one or more Deployables, one or more
       Control Path interfaces, and one or more attach handles.
    """
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True, unique=True)
    # TODO: type should be an enum.
    type = Column(String(30), nullable=False) # e.g. "GPU","FPGA".
    vendor = Column(String(255), nullable=False)
    model = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=False)
    # board-level info etc. will go here.

class Deployable(Base):
    """Equivalent of a Resource Provider. Contains one or more resources."""

    __tablename__ = 'deployables'
    __table_args__ = (
        schema.UniqueConstraint('uuid', name='uniq_deployables0uuid'),
        table_args()
    )

    id = Column(Integer, primary_key=True, unique=True)
    uuid = Column(String(36), unique=True, nullable=False)
    parent_uuid = Column(String(36),
                         ForeignKey('deployables.uuid'), nullable=True)
    root_uuid = Column(String(36),
                       ForeignKey('deployables.uuid'), nullable=True)

    device_id = Column(Integer,
                    ForeignKey('devices.id', ondelete="RESTRICT"),
                    nullable=False)
    num_accelerators = Column(Integer)

class ControlPathID(Base):
    """ An identifier for a control path interface to the device.
        E.g. PCI PF. A device may have more than one of these, in which
        case the Cyborg driver needs to know how to handle these.
    """
    __tablename__ = 'controlpath_ids'

    id = Column(Integer, primary_key=True, unique=True)
    type_name = Column(String(30), nullable=False) # e.g. 'PCI', 'PowerVm.*'
    device_id = Column(Integer,
                    ForeignKey('devices.id', ondelete="RESTRICT"),
                    nullable=False)
    # Depending on type_name, the specifics of the Control Path Interface
    # would be in this JSON dictionary. For standard PCI, the fields would be:
    # 'domain', 'bus', 'device' and 'function'.
    info = Column(String(255), nullable=False)

class AttachHandle(Base):
    """ An identifer for an object by which an accelerator is
        attached to an instance (VM). E.g. PCI PF.
    """
    __tablename__ = 'attach_handles'

    id = Column(Integer, primary_key=True, unique=True)
    type_name = Column(String(255), nullable=False)
    device_id = Column(Integer,
        ForeignKey('devices.id', ondelete="RESTRICT"),
        nullable=False)
    in_use = Column(Boolean, default=False)
    # Depending on type_name, the specifics of the Control Path Interface
    # would be in this JSON dictionary. For standard PCI, the fields would be:
    # 'domain', 'bus', 'device' and 'function'.
    info = Column(String(255), nullable=False)

class Attribute(Base):
    """ Attributes are properties of Deployables in key-value pair format."""
    __tablename__ = 'attributes'
    __table_args__ = (
        schema.UniqueConstraint('uuid', name='uniq_attributes0uuid'),
        Index('attributes_deployable_id_idx', 'deployable_id'),
        table_args()
    )

    id = Column(Integer, primary_key=True, unique=True)
    uuid = Column(String(36), unique=True, nullable=False)
    deployable_id = Column(Integer,
                           ForeignKey('deployables.id', ondelete="CASCADE"),
                           nullable=False)
    key = Column(Text, nullable=False)
    value = Column(Text, nullable=False)

class QuotaUsage(Base):
    """Represents the current usage for a given resource."""

    __tablename__ = 'quota_usages'
    __table_args__ = (
        Index('ix_quota_usages_project_id', 'project_id'),
        Index('ix_quota_usages_user_id', 'user_id'),
    )
    id = Column(Integer, primary_key=True)

    project_id = Column(String(255))
    user_id = Column(String(255))
    resource = Column(String(255), nullable=False)

    in_use = Column(Integer, nullable=False)
    reserved = Column(Integer, nullable=False)

    @property
    def total(self):
        return self.in_use + self.reserved

    until_refresh = Column(Integer)

class Reservation(Base):
    """Represents a resource reservation for quotas."""

    __tablename__ = 'reservations'
    __table_args__ = (
        Index('ix_reservations_project_id', 'project_id'),
        Index('reservations_uuid_idx', 'uuid'),
        Index('ix_reservations_user_id', 'user_id'),
    )
    id = Column(Integer, primary_key=True, nullable=False)
    uuid = Column(String(36), nullable=False)

    usage_id = Column(Integer, ForeignKey('quota_usages.id'), nullable=False)

    project_id = Column(String(255))
    user_id = Column(String(255))
    resource = Column(String(255))

    delta = Column(Integer, nullable=False)
    expire = Column(DateTime)

    usage = orm.relationship(
        "QuotaUsage",
        foreign_keys=usage_id,
        primaryjoin=usage_id == QuotaUsage.id)

class DeviceProfile(Base):
    """ A device profile is a set of requirements for accelerators.
        See https://review.openstack.org/#/c/602978/
    """
    __tablename__ = 'device_profiles'

    def __str__(self):
       s = "id: (%s) uuid: (%s) name: (%s) json: (%s)" % (
               self.id, self.uuid, self.name, self.json
           )
       return s

    id = Column(Integer, primary_key=True, unique=True, nullable=False)
    uuid = Column(String(36), nullable=False, unique=True)
    name=Column(String(255), nullable=False, unique=True)
    json = Column(String(1000))

# NOTE on ARQs and ExtARQs
# An ExtARQ is a Cyborg object that wraps an ARQ with Cyborg-private fields.
# It corresponds 1:1 with ARQ. They are represented as db tables and also
# as OVos. In both cases, we use composition rather than inheritance, i.e.,
# the ExtARQ object includes an ARQ as a field rather than extend it as a
# class.

class ExtARQ(Base):
    """ Cyborg object that wraps an ARQ with Cyborg-private fields.
        See note above.
    """

    __tablename__ = 'extarqs'
    id = Column(Integer, primary_key=True, unique=True, nullable=False)
    # ARQ fields begin here
    uuid = Column(String(36), unique=True, nullable=False)
    state = Column(String(36), nullable=False) # TODO: shd be an enum
    device_profile_id = Column(Integer,
        ForeignKey('device_profiles.id', ondelete="RESTRICT"),
        nullable=False)
    host_name = Column(String(255), nullable=True)
    device_rp_uuid = Column(String(255), nullable=True)
    instance_uuid = Column(String(255), nullable=True)
    attach_handle_id = Column(Integer,
        ForeignKey('attach_handles.id', ondelete="RESTRICT"), nullable=True)
    # ARQ fields end here. Following are Cyborg-private fields.

    deployable_id = Column(Integer,
        ForeignKey('deployables.id', ondelete="RESTRICT"), nullable=True)
    substate = Column(String(255), default='Initial') # TODO shd be enum
