#!/bin/bash

create_arqs() {
   curl -H "Content-Type: application/json" -X POST -d '{"device_profile_name": "devprof.1"}' http://192.168.122.4/accelerator/v1/arqs
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

   curl -H "Content-Type: application/json" -X POST -d "$body" http://192.168.122.4/accelerator/v1/arq_bindings
   /bin/rm -f /tmp/arq_binding_json.txt
}

# create_arqs
post_bindings
