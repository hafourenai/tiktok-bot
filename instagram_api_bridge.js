const { IgApiClient } = require("instagram-private-api");

const args = process.argv.slice(2);
if (args.length === 0) {
  process.stderr.write("Usage: node instagram_api_bridge.js <action|url> [username] [password]\n");
  process.exit(2);
}

const isExplicitAction = ["download", "info"].includes(args[0]);
const action = isExplicitAction ? args[0] : "download";
const param1 = isExplicitAction ? args[1] : args[0];
const param2 = isExplicitAction ? args[2] : args[1];

function extractMediaId(url) {
  // Handle different Instagram URL formats:
  // https://www.instagram.com/p/ABC123/
  // https://www.instagram.com/reel/ABC123/
  // https://www.instagram.com/tv/ABC123/
  // https://www.instagram.com/stories/username/ABC123/
  const match = url.match(/(?:p|reel|tv|stories\/\w+)\/([A-Za-z0-9_-]+)/);
  return match ? match[1] : null;
}

function decodeMediaId(encodedId) {
  // Instagram uses base64-like encoding for media IDs
  // Convert URL-safe base64 to standard, then decode
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  let num = 0n;
  for (const c of encodedId) {
    num = num * 64n + BigInt(alphabet.indexOf(c));
  }
  return num.toString();
}

async function handleDownload(url, username, password) {
  if (!username || !password) {
    process.stderr.write("Instagram credentials required: INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD env vars\n");
    process.exit(2);
  }

  try {
    const ig = new IgApiClient();
    ig.state.generateDevice(username);
    ig.request.end$.subscribe(() => {
      // Cleanup subscription
    });

    // Login
    await ig.account.login(username, password);

    // Extract media ID
    const shortcode = extractMediaId(url);
    if (!shortcode) {
      process.stderr.write("Could not extract media ID from URL\n");
      process.exit(1);
    }

    // Fetch media info
    const media = await ig.media.shortcode.info(shortcode);

    if (!media) {
      process.stderr.write("Media not found or is private\n");
      process.exit(1);
    }

    // Extract download URL based on media type
    let downloadUrl = null;
    let mediaType = "unknown";

    if (media.video_url) {
      // Video or Reel
      downloadUrl = media.video_url;
      mediaType = media.media_type === 8 ? "carousel" : "video";
    } else if (media.image_versions2?.candidates?.[0]?.url) {
      // Photo
      downloadUrl = media.image_versions2.candidates[0].url;
      mediaType = "photo";
    } else if (media.carousel_media?.[0]) {
      // Carousel - download first item
      const firstItem = media.carousel_media[0];
      if (firstItem.video_url) {
        downloadUrl = firstItem.video_url;
        mediaType = "carousel_video";
      } else if (firstItem.image_versions2?.candidates?.[0]?.url) {
        downloadUrl = firstItem.image_versions2.candidates[0].url;
        mediaType = "carousel_photo";
      }
    }

    if (!downloadUrl) {
      process.stderr.write("Could not extract download URL from media\n");
      process.exit(1);
    }

    const response = {
      status: "success",
      url: downloadUrl,
      mediaType: mediaType,
      caption: media.caption?.text || "",
      uploadedBy: media.user?.username || "unknown",
    };

    process.stdout.write(JSON.stringify(response));
  } catch (err) {
    const message = err?.message || "Failed to download Instagram media";
    // Check for specific errors
    if (message.includes("401") || message.includes("Invalid")) {
      process.stderr.write("Invalid Instagram credentials or account is restricted\n");
    } else if (message.includes("429")) {
      process.stderr.write("Rate limited by Instagram. Wait and try again later\n");
    } else if (message.includes("challenge")) {
      process.stderr.write("Account needs verification (2FA or security challenge). Login manually first\n");
    } else {
      process.stderr.write(`${message}\n`);
    }
    process.exit(1);
  }
}

async function handleInfo(url, username, password) {
  if (!username || !password) {
    process.stderr.write("Instagram credentials required: INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD env vars\n");
    process.exit(2);
  }

  try {
    const ig = new IgApiClient();
    ig.state.generateDevice(username);
    ig.request.end$.subscribe(() => {
      // Cleanup subscription
    });

    await ig.account.login(username, password);

    const shortcode = extractMediaId(url);
    if (!shortcode) {
      process.stderr.write("Could not extract media ID from URL\n");
      process.exit(1);
    }

    const media = await ig.media.shortcode.info(shortcode);

    if (!media) {
      process.stderr.write("Media not found or is private\n");
      process.exit(1);
    }

    const response = {
      status: "success",
      mediaId: media.id,
      mediaType: media.media_type,
      uploadedBy: media.user?.username || "unknown",
      caption: media.caption?.text || "",
      likes: media.like_count || 0,
      comments: media.comment_count || 0,
      timestamp: media.taken_at || null,
      isVideo: media.media_type === 2 || media.media_type === 8,
      isCarousel: media.media_type === 8,
      itemCount: media.carousel_media?.length || 1,
    };

    process.stdout.write(JSON.stringify(response));
  } catch (err) {
    const message = err?.message || "Failed to get Instagram media info";
    process.stderr.write(`${message}\n`);
    process.exit(1);
  }
}

(async () => {
  const username = process.env.INSTAGRAM_USERNAME || param2;
  const password = process.env.INSTAGRAM_PASSWORD || null;

  if (action === "download") {
    await handleDownload(param1, username, password);
  } else if (action === "info") {
    await handleInfo(param1, username, password);
  } else {
    process.stderr.write(`Unknown action: ${action}\n`);
    process.exit(2);
  }
})();
