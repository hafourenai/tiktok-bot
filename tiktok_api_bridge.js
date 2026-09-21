const { Downloader } = require("@tobyg74/tiktok-api-dl");

const url = process.argv[2];
if (!url) process.exit(2);

(async () => {
  for (const version of ["v1", "v2", "v3"]) {
    try {
      const response = await Downloader(url, { version });
      const video = response?.result?.video;
      const candidates = [
        ...(video?.playAddr || []),
        ...(video?.downloadAddr || []),
        video?.videoHD,
        video?.videoWatermark,
        response?.result?.direct,
      ].filter((value) => typeof value === "string" && value.startsWith("http"));
      if (response?.status === "success" && candidates.length) {
        process.stdout.write(JSON.stringify({ url: candidates[0], version }));
        return;
      }
    } catch (_) {
      // Try the next provider version.
    }
  }
  process.stderr.write("The unofficial TikTok providers returned no video URL\n");
  process.exit(1);
})();
