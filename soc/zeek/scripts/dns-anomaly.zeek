module Lab;
export {
 redef enum Notice::Type += { Long_DNS_Query, High_Entropy_DNS, Lab_HTTP_Beacon };
}
event dns_request(c: connection, msg: dns_msg, query: string, qtype: count, qclass: count)
 {
 if ( |query| > 80 )
  NOTICE([$note=Long_DNS_Query, $conn=c, $msg=fmt("Long DNS query (%d): %s", |query|, query), $identifier=cat(c$id$orig_h, query)]);
 local labels = split_string(query, /\./);
 if ( |labels| > 0 && |labels[0]| >= 32 && find_entropy(labels[0])$entropy > 3.5 )
  NOTICE([$note=High_Entropy_DNS, $conn=c, $msg=fmt("High entropy DNS label: %s", query), $identifier=cat(c$id$orig_h, query)]);
 }
event http_header(c: connection, is_orig: bool, name: string, value: string)
 {
 if ( is_orig && name == "USER-AGENT" && value == "LabBeacon/1.0" )
  NOTICE([$note=Lab_HTTP_Beacon, $conn=c, $msg="Synthetic lab HTTP beacon", $identifier=cat(c$id$orig_h)]);
 }
