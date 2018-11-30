#!/bin/bash

create_devprof() {
   cat <<EOF > /tmp/devprof.txt
   { "name": "mydevprof.2",
     "json": "{ }"
   }
EOF
   body=`cat /tmp/devprof.txt`

   echo "body:" "${body}"
   curl -H "Content-Type: application/json" -X POST -d "$body" \
        http://192.168.122.4/accelerator/v2/device_profiles
   /bin/rm -f /tmp/devprof.txt
}


create_arqs() {
   curl -H "Content-Type: application/json" -X POST -d '{"device_profile_name": "devprof.1"}' http://192.168.122.4/accelerator/v2/arqs
}

post_bindings() {
   cat <<EOF > /tmp/arq_binding_json.txt
   { "bindings": 
     [
        { "arq_uuid":   "335f1945-5c32-4f88-8980-104b698fe585",
          "host_name":  "cynova",
          "device_rp_uuid": "6026b395-be7b-426f-8baa-ca882797:q07fda",
          "instance_uuid": "bfaa837d-1ab5-4fd8-90eb-94008f2919ae"
        }
      ]
   }
EOF
   body=`cat /tmp/arq_binding_json.txt`

   curl -H "Content-Type: application/json" -X POST -d "$body" http://192.168.122.4/accelerator/v2/arq_bindings
   /bin/rm -f /tmp/arq_binding_json.txt
}

create_devprof
# create_arqs
# post_bindings
