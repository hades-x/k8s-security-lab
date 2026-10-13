module Lab;
export { redef enum Notice::Type += { Port_Scan }; }
global ports: table[addr, addr] of set[port] &write_expire=1min;
event new_connection(c: connection)
 {
 if ( c$id$resp_p !in set( 53/udp, 80/tcp, 8080/tcp, 443/tcp ) )
  {
  if ( [c$id$orig_h, c$id$resp_h] !in ports )
   ports[c$id$orig_h, c$id$resp_h] = set();
  add ports[c$id$orig_h, c$id$resp_h][c$id$resp_p];
  if ( |ports[c$id$orig_h, c$id$resp_h]| >= 12 )
   NOTICE([$note=Port_Scan, $conn=c, $msg="At least 12 destination ports within one minute", $identifier=cat(c$id$orig_h,c$id$resp_h)]);
  }
 }
