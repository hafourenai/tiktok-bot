const { Downloader } = require("./youtube_api_dl");

const url = process.argv[2];
const version = process.argv[3] || "v1";

if (!url) {
  process.stderr.write("Usage: node youtube_api_bridge.js <url> [version]\n");
  process.exit(2);
}

(async () => {
  try {
    const response = await Downloader(url, { version });
    process.stdout.write(JSON.stringify(response));
  } catch (error) {
    process.stderr.write(`Error: ${error.message}\n`);
    process.exit(1);
  }
})();
