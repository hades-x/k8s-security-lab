@load base/protocols/conn
@load base/protocols/dns
@load base/protocols/http
redef LogAscii::use_json = T;
redef Log::default_rotation_interval = 1hr;
# Lab-only: every guarded replay must produce fresh notices for acceptance.
# Production deployments should retain suppression and tune correlation windows.
redef Notice::default_suppression_interval = 0sec;
redef Site::local_nets += { 192.168.150.0/24, 10.42.0.0/16, 10.43.0.0/16 };
