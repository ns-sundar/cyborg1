"""Add-dev-prof

Revision ID: 40ec6cd9e20a
Revises: d6f033d8fa5b
Create Date: 2018-11-20 02:06:43.448469

"""

# revision identifiers, used by Alembic.
revision = '40ec6cd9e20a'
down_revision = 'd6f033d8fa5b'

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.drop_table('attributes') # HACK: Attributes table needs to be set up.
    op.drop_table('deployables')
    op.drop_table('accelerators')

    op.create_table('devices',
      sa.Column('id',sa.Integer(), nullable=False, primary_key=True),
      sa.Column('type', sa.String(length=30), nullable=False),
      sa.Column('vendor', sa.String(length=255), nullable=False),
      sa.Column('model', sa.String(length=255), nullable=False),
      sa.Column('hostname', sa.String(length=255), nullable=False)
    )

    op.create_table('deployables',
      sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
      sa.Column('uuid', sa.String(length=36), unique=True, nullable=False),
      sa.Column('parent_uuid', sa.String(length=36),
                sa.ForeignKey('deployables.uuid', ondelete='CASCADE')),
      sa.Column('root_uuid', sa.String(length=36),
                sa.ForeignKey('deployables.uuid', ondelete='CASCADE')),
      sa.Column('device_id', sa.Integer(),
                sa.ForeignKey('devices.id', ondelete='CASCADE'),
                nullable=False),
      sa.Column('num_accelerators', sa.Integer())
    )

    op.create_table('controlpath_ids',
      sa.Column('id',sa.Integer(), nullable=False, primary_key=True),
      sa.Column('type_name', sa.String(length=30), nullable=False),
      sa.Column('device_id', sa.Integer,
                sa.ForeignKey('devices.id', ondelete='CASCADE'),
                unique=True, nullable=False)
    )

    op.create_table('controlpath_ids_pci',
      sa.Column('id', sa.Integer,
                 sa.ForeignKey('controlpath_ids.id', ondelete='CASCADE'),
                 unique=True, nullable=False),
      sa.Column('domain', sa.Integer, nullable=False),
      sa.Column('bus', sa.Integer, nullable=False),
      sa.Column('device', sa.Integer, nullable=False),
      sa.Column('function', sa.Integer, nullable=False),
    )

    op.create_table('attach_handles',
      sa.Column('id',sa.Integer(), nullable=False, primary_key=True),
      sa.Column('type_name', sa.String(length=255), nullable=False),
      sa.Column('device_id', sa.Integer, nullable=False)
    )

    op.create_table('attach_handles_pci',
      sa.Column('id', sa.Integer,
                 sa.ForeignKey('attach_handles.id', ondelete='CASCADE'),
                 unique=True, nullable=False),
      sa.Column('domain', sa.Integer, nullable=False),
      sa.Column('bus', sa.Integer, nullable=False),
      sa.Column('device', sa.Integer, nullable=False),
      sa.Column('function', sa.Integer, nullable=False)
    )

    op.create_table('device_profiles',
      sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
      sa.Column('name', sa.String(length=255), nullable=False, unique=True),
      sa.Column('json', sa.String(length=1000), nullable=True),
    )

    op.create_table('arqs',
      sa.Column('id',sa.Integer(), nullable=False, primary_key=True),
      sa.Column('uuid', sa.String(length=36), unique=True, nullable=False),
      sa.Column('state', sa.String(length=36), nullable=False) ,
      sa.Column('device_profile_id',sa.Integer, nullable=False),
      sa.Column('host_name', sa.String(length=255)),
      sa.Column('device_rp_uuid', sa.String(length=255)),
      sa.Column('instance_uuid', sa.String(length=255))
    )

    op.create_table('extarqs',
      sa.Column('id',sa.Integer(),
                 sa.ForeignKey('arqs.id', ondelete='CASCADE'),
                 unique=True, nullable=False),
      sa.Column('arq_uuid',sa.Integer, nullable=False)
    )
