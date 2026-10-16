Verify downloads in a private staging directory before adding them to the reusable wheel cache. Select the downloaded
archive from that directory instead of pip's output. The pip seeder now uses the same download verification path and
installs the selected local wheels without another index lookup.
