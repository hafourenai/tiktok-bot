const { spawn } = require("child_process");
const path = require("path");

async function spawnYtDlp(url, extraArgs = []) {
  return new Promise((resolve, reject) => {
    const args = [
      "--dump-single-json",
      "--no-playlist",
      "--no-warnings",
      "--quiet",
      ...extraArgs,
      url,
    ];

    const venvPython = path.join(__dirname, "venv", "Scripts", "python.exe");
    let child;
    
    try {
      child = spawn(venvPython, ["-m", "yt_dlp", ...args], {
        stdio: ["ignore", "pipe", "pipe"],
        timeout: 60000,
      });
    } catch (e) {
      reject(new Error(`Failed to spawn venv python: ${e.message}`));
      return;
    }

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    child.on("close", (code) => {
      if (code === 0) {
        try {
          const json = JSON.parse(stdout);
          resolve(json);
        } catch (e) {
          reject(new Error("Failed to parse yt-dlp JSON output"));
        }
      } else {
        reject(new Error(stderr.trim() || "yt-dlp failed"));
      }
    });

    child.on("error", (err) => {
      reject(new Error(`Failed to spawn yt-dlp: ${err.message}`));
    });
  });
}

function selectFormat(formats, quality) {
  if (!Array.isArray(formats) || formats.length === 0) {
    return null;
  }

  const mp4Formats = formats
    .filter((f) => f.vcodec && f.vcodec !== "none" && f.ext === "mp4")
    .sort((a, b) => (b.height || 0) - (a.height || 0));

  if (quality === "v1") {
    const merged = mp4Formats.filter(
      (f) => f.acodec && f.acodec !== "none" && (f.height || 0) <= 720
    );
    return merged.length > 0 ? merged[0] : null;
  }

  if (quality === "v2") {
    return mp4Formats.length > 0 ? mp4Formats[0] : null;
  }

  if (quality === "v3") {
    const small = mp4Formats.filter((f) => (f.height || 0) <= 360);
    return small.length > 0 ? small[0] : small[mp4Formats.length - 1];
  }

  return null;
}

async function Downloader(url, options = {}) {
  const { version = "v1" } = options;

  try {
    const info = await spawnYtDlp(url);

    if (!info.id || !info.title) {
      return { status: "error", error: "Invalid video response" };
    }

    const formats = info.formats || [];
    const selectedFormat = selectFormat(formats, version);

    if (!selectedFormat) {
      return { status: "error", error: `No suitable format found for ${version}` };
    }

    const videoUrl = selectedFormat.url || info.url;
    if (!videoUrl) {
      return { status: "error", error: "No direct URL available" };
    }

    return {
      status: "success",
      version,
      result: {
        meta: {
          id: info.id,
          title: info.title,
          duration: info.duration || 0,
          thumbnail: info.thumbnail || null,
          channel: info.uploader || null,
        },
        video: {
          url: videoUrl,
          quality: `${selectedFormat.height || 0}p`,
          format: selectedFormat.ext || "mp4",
          sizeBytes: selectedFormat.filesize || 0,
        },
        formats: formats.slice(0, 10).map((f) => ({
          format_id: f.format_id,
          quality: `${f.height || 0}p`,
          ext: f.ext,
          vcodec: f.vcodec || "none",
          acodec: f.acodec || "none",
          filesize: f.filesize || 0,
        })),
      },
    };
  } catch (error) {
    return {
      status: "error",
      error: error.message || "Unknown error occurred",
    };
  }
}

module.exports = { Downloader };
