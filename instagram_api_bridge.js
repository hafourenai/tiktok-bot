const { IgApiClient } = require("instagram-private-api");

const args = process.argv.slice(2);
if (require.main === module && args.length === 0) {
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
  const parsed = new URL(url);
  if (!['instagram.com', 'www.instagram.com'].includes(parsed.hostname) ||
      !['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('Invalid Instagram URL');
  }
  const match = parsed.pathname.match(/^\/(?:p|reel|tv)\/([A-Za-z0-9_-]+)\/?$/);
  if (match) return decodeMediaId(match[1]);
  const story = parsed.pathname.match(/^\/stories\/[A-Za-z0-9_.]+\/(\d+)\/?$/);
  return story ? story[1] : null;
}

function decodeMediaId(encodedId) {
  // Instagram uses base64-like encoding for media IDs
  // Convert URL-safe base64 to standard, then decode
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  let num = 0n;
  for (const c of encodedId) {
    if (!alphabet.includes(c)) throw new Error('Invalid Instagram shortcode');
    num = num * 64n + BigInt(alphabet.indexOf(c));
  }
  return num.toString();
}

async function fetchMedia(ig, url) {
  const mediaId = extractMediaId(url);
  if (!mediaId) throw new Error('Invalid Instagram media URL');
  const response = await ig.media.info(mediaId);
  const media = response?.items?.[0];
  if (!media) throw new Error('Media not found or unavailable to this account');
  return media;
}

function selectDownload(media) {
  const item = media.carousel_media?.[0] || media;
  const videos = (item.video_versions || []).filter(v => v.url);
  const images = (item.image_versions2?.candidates || []).filter(v => v.url);
  const candidates = videos.length ? videos : images;
  candidates.sort((a, b) => (b.width || 0) * (b.height || 0) - (a.width || 0) * (a.height || 0));
  if (!candidates.length) throw new Error('No downloadable media URL returned');
  return {url: candidates[0].url, mediaType: videos.length ? 'video' : 'photo'};
}

function describeError(err) {
  const message = `${err?.name || ''} ${err?.message || ''}`.toLowerCase();
  if (/twofactor|two.factor|challenge|checkpoint/.test(message)) {
    return 'Instagram requires verification (2FA or security challenge).';
  }
  if (/429|ratelimit|rate limit|please wait/.test(message)) {
    return 'Rate limited by Instagram. Wait before trying again.';
  }
  if (/login|password|credential|401/.test(message)) {
    return 'Instagram login failed. Check credentials or account restrictions.';
  }
  if (/invalid.*url/.test(message)) return 'Invalid Instagram media URL.';
  if (/404|not found|unavailable/.test(message)) return 'Media unavailable to this account.';
  return 'Instagram API request failed. Public media can still be blocked by Instagram.';
}

async function handleDownload(url, username, password) {
  if (!username || !password) {
    process.stderr.write("Instagram credentials required: INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD env vars\n");
    process.exit(2);
  }

  try {
    const ig = new IgApiClient();
    ig.state.generateDevice(username);

    // Login
    await ig.account.login(username, password);

    const media = await fetchMedia(ig, url);

    const response = {
      status: "success",
      ...selectDownload(media),
      caption: media.caption?.text || "",
      uploadedBy: media.user?.username || "unknown",
    };

    process.stdout.write(JSON.stringify(response));
  } catch (err) {
    process.stderr.write(describeError(err) + '\n');
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

    await ig.account.login(username, password);

    const media = await fetchMedia(ig, url);

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
    process.stderr.write(describeError(err) + '\n');
    process.exit(1);
  }
}

module.exports = {extractMediaId, decodeMediaId, fetchMedia, selectDownload};

if (require.main === module) (async () => {
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
