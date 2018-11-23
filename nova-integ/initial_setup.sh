#!/bin/bash

setup_db() {
   local TMP_DEV_PROF="/tmp/device-profiles.txt"
   cat <<EOF > $TMP_DEV_PROF
   { 'version' : '1.0',
     'groups'  : [
         { 'resources:CUSTOM_ACCELERATOR_FPGA=1',
           'trait:CUSTOM_FPGA_INTEL_PAC_ARRIA10=required',
           'trait:CUSTOM_FUNCTION_91855328_7C3B_4EEC_BDD7_B3F4650CE320=required'
         }
     ]
   }
EOF
   local dev_prof=\"`cat $TMP_DEV_PROF | tr -s '\n' ' '`\"
   echo "dev_prof:" $dev_prof

   # Simple db setup with only one row in each table
   local TMP_SCRIPT="/tmp/setup-db.txt"
   cat <<EOF > $TMP_SCRIPT
   use cyborg;
   DELETE FROM device_profiles;
   DELETE FROM attach_handles_pci;
   DELETE FROM attach_handles;
   DELETE FROM controlpath_ids_pci;
   DELETE FROM controlpath_ids;
   DELETE FROM deployables;
   DELETE FROM devices;
   INSERT INTO devices (type,vendor,model,hostname)
      VALUES ('FPGA', 'Intel', 'PAC Arria 10', 'cy-nova');
   INSERT INTO deployables (uuid, num_accelerators, device_id)
      SELECT '6026b395-be7b-426f-8baa-ca88279707fd', 1,
             id FROM devices WHERE type = 'FPGA';
   INSERT INTO controlpath_ids (type_name, device_id)
      SELECT 'PCI', id FROM devices WHERE type = 'FPGA';
   INSERT INTO controlpath_ids_pci (domain, bus, device, function, id)
      SELECT 0, 0x5E, 0, 0,
             id FROM controlpath_ids WHERE type_name = 'PCI';   
   INSERT INTO attach_handles (type_name, device_id)
      SELECT 'PCI', id FROM devices WHERE type = 'FPGA';
   INSERT INTO attach_handles_pci (domain, bus, device, function, id)
      SELECT 0, 0x5E, 0, 0,
             id FROM attach_handles WHERE type_name = 'PCI';   
   INSERT INTO device_profiles (name,json,uuid) 
      VALUES ('devprof.1', $dev_prof,
              'aee9ffb0-b59a-498c-aa93-7b7da06a0e6e');
EOF

   set -x
   mysql -u root -e "$(cat $TMP_SCRIPT)"
   set +x
   /bin/rm -f $TMP_SCRIPT $TMP_DEV_PROF
}

setup_placement() {
   local rc='CUSTOM_ACCELERATOR_FPGA'
   local rp='FPGA_Intel_PAC_Arria10_1'
   local trait1="CUSTOM_FPGA_INTEL_PAC_ARRIA10"
   local trait2="CUSTOM_FUNCTION_91855328_7C3B_4EEC_BDD7_B3F4650CE320"

   # Placement endpoint URL
   local endpt=`openstack endpoint list -c URL -f value | grep place`
   echo Placement URL: ${endpt}

   # Set up your authentication in CURL_AUTH variable if needed
   local CURL_AUTH="X-Auth-Token: "
   CURL_AUTH="$CURL_AUTH ${MY_TOKEN}"
   local VER="OpenStack-API-Version: placement 1.30"
   local CTYPE="Content-Type: application/json"
   local CURL="curl -sSLf -H \"${CURL_AUTH}\" -H \"${VER}\""
   local POST="$CURL -H \"${CTYPE}\" -d"
   local PUT="$CURL -H \"${CTYPE}\" -X PUT"

   echo "Create custom RC"
   eval $POST \'{\"name\": \"$rc\"}\' ${endpt}/resource_classes

   echo "Create traits"
   eval $PUT ${endpt}/traits/$trait1
   eval $PUT ${endpt}/traits/$trait2

   echo "Create RP"
   # Assume only 1 compute node; get its rp uuid
   local cn_uuid=$(eval $CURL "${endpt}/resource_providers\?name=$HOSTNAME" | \
      python -c 'import sys, json; r=json.load(sys.stdin); print r["resource_providers"][0]["uuid"]')
   echo "   Compute node UUID: " $cn_uuid
   
   local body="{\"name\": \"$rp\", \"parent_provider_uuid\": \"$cn_uuid\"}"
   local rp_create_out=$(eval $POST \'$body\' ${endpt}/resource_providers)
   local status=$?
   local dev_rp_uuid=""
   [[ $status -eq 0 ]] && \
      dev_rp_uuid=$(echo $rp_create_out | 
        python -c 'import sys, json; r=json.load(sys.stdin); print r["uuid"]')
   echo "Device RP UUID: " $dev_rp_uuid

   echo "Apply traits to the device RP"
   body="{\"resource_provider_generation\": 0,
          \"traits\": [\"$trait1\",\"$trait2\"]}"
   url="${endpt}/resource_providers/${dev_rp_uuid}/traits"
   eval $PUT -d \'$body\' $url

   echo "Populate inventory for device RP"
   body="{\"resource_provider_generation\": 1, \"total\": 1}"
   url="${endpt}/resource_providers/${dev_rp_uuid}/inventories/$rc" 
   set -x
   eval $PUT -d \'$body\' $url
   set +x
}

#### Main
setup_db
setup_placement
