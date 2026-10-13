@load /scripts/local.zeek
@load frameworks/intel/seen
@load frameworks/intel/do_notice
@load /scripts/dns-anomaly.zeek
@load /scripts/scan.zeek
# A valid header-only TSV is installed even when no indicators exist.
redef Intel::read_files += { "/intel/misp.intel" };
redef Intel::item_expiration = 20min;
