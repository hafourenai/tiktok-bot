const https = require("https");
const tiktok = require("@tobyg74/tiktok-api-dl");

const args = process.argv.slice(2);
if (args.length === 0) {
  process.stderr.write("Usage: node tiktok_api_bridge.js <action|url> [param1] [param2]\n");
  process.exit(2);
}

const isExplicitAction = ["download", "stalk", "posts", "reposts"].includes(args[0]);
const action = isExplicitAction ? args[0] : "download";
const param1 = isExplicitAction ? args[1] : args[0];
const param2 = isExplicitAction ? args[2] : args[1];

function cleanUsername(input) {
  if (!input) return "";
  return input.trim().replace(/^@/, "").replace(/\/$/, "");
}

async function handleDownload(url) {
  for (const version of ["v1", "v2", "v3"]) {
    try {
      const response = await tiktok.Downloader(url, { version });
      const video = response?.result?.video;
      const candidates = [
        ...(video?.playAddr || []),
        ...(video?.downloadAddr || []),
        video?.videoHD,
        video?.videoWatermark,
        response?.result?.direct,
      ].filter((value) => typeof value === "string" && value.startsWith("http"));
      if (response?.status === "success" && candidates.length) {
        process.stdout.write(JSON.stringify({ status: "success", url: candidates[0], version }));
        return;
      }
    } catch (_) {
      // Try next version
    }
  }
  process.stderr.write("The unofficial TikTok providers returned no video URL\n");
  process.exit(1);
}

function fetchMetaProfile(username) {
  return new Promise((resolve, reject) => {
    const req = https.get(
      `https://www.tiktok.com/@${username}`,
      {
        headers: {
          "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
          Accept: "text/html",
        },
      },
      (res) => {
        let html = "";
        res.on("data", (c) => (html += c));
        res.on("end", () => {
          try {
            const getMeta = (prop) => {
              const regex = new RegExp('<meta\\s+(?:property|name)=["\']' + prop + '["\']\\s+content=["\'](.*?)["\']', "i");
              const m = html.match(regex);
              return m ? m[1] : "";
            };
            const title = getMeta("og:title") || getMeta("twitter:title") || "";
            const desc = getMeta("og:description") || getMeta("twitter:description") || "";
            const image = getMeta("og:image") || getMeta("twitter:image") || getMeta("lark:url:video_cover_image_url") || "";

            if (!title && !desc) {
              return resolve(null);
            }

            const nickname = title.replace(/\s+on TikTok$/i, "").trim() || username;
            const matchStats = desc.match(
              /([\d\.,]+[KkMmBb]?)\s+Followers,\s+([\d\.,]+[KkMmBb]?)\s+Following,\s+([\d\.,]+[KkMmBb]?)\s+Likes(?:\s*-\s*(.*))?/i
            );
            let followers = "0";
            let following = "0";
            let likes = "0";
            let signature = "";
            if (matchStats) {
              followers = matchStats[1];
              following = matchStats[2];
              likes = matchStats[3];
              signature = matchStats[4] || "";
            }

            resolve({
              status: "success",
              result: {
                user: {
                  username: username,
                  nickname: nickname,
                  avatarLarger: image.replace(/&amp;/g, "&"),
                  signature: signature,
                  verified: html.includes("verified"),
                },
                stats: {
                  followerCount: followers,
                  followingCount: following,
                  heartCount: likes,
                  videoCount: "-",
                },
              },
            });
          } catch (e) {
            reject(e);
          }
        });
      }
    );
    req.on("error", reject);
  });
}

async function handleStalk(username) {
  const user = cleanUsername(username);
  if (!user) {
    process.stderr.write("Username is required for stalk\n");
    process.exit(2);
  }
  try {
    const metaRes = await fetchMetaProfile(user);
    if (metaRes && metaRes.status === "success") {
      process.stdout.write(JSON.stringify(metaRes));
      return;
    }
  } catch (_) {
    // Fallback to library
  }

  try {
    const res = await tiktok.StalkUser(user);
    if (res?.status === "success" && res?.result?.user) {
      process.stdout.write(JSON.stringify(res));
    } else {
      process.stderr.write(res?.message || "User not found or profile is private\n");
      process.exit(1);
    }
  } catch (err) {
    process.stderr.write(err?.message || "Failed to stalk TikTok user\n");
    process.exit(1);
  }
}

async function handlePosts(username, limitStr) {
  const user = cleanUsername(username);
  const limit = parseInt(limitStr, 10) || 5;
  if (!user) {
    process.stderr.write("Username is required for posts\n");
    process.exit(2);
  }
  try {
    if (typeof tiktok.GetUserPosts === "function") {
      const res = await tiktok.GetUserPosts(user, { postLimit: limit });
      if (res?.status === "success" && Array.isArray(res?.result)) {
        process.stdout.write(JSON.stringify(res));
        return;
      }
    }
  } catch (_) {
    // Fallback to metadata scraper
  }

  try {
    const metaRes = await fetchMetaProfile(user);
    if (metaRes && metaRes.status === "success") {
      process.stdout.write(JSON.stringify({
        status: "success",
        result: [{
          id: "1",
          desc: metaRes.result.user.signature,
          stats: { playCount: 0, likeCount: 0, commentCount: 0 }
        }],
        message: "Data terbatas dari metadata profil"
      }));
      return;
    }
  } catch (_) {}

  process.stderr.write("Fitur postingan sedang dibatasi oleh sistem anti-bot TikTok\n");
  process.exit(1);
}

async function handleReposts(username, limitStr) {
  const user = cleanUsername(username);
  if (!user) {
    process.stderr.write("Username is required for reposts\n");
    process.exit(2);
  }
  process.stderr.write("Fitur repostan TikTok tidak tersedia\n");
  process.exit(1);
}

(async () => {
  if (action === "download") {
    await handleDownload(param1);
  } else if (action === "stalk") {
    await handleStalk(param1);
  } else if (action === "posts") {
    await handlePosts(param1, param2);
  } else if (action === "reposts") {
    await handleReposts(param1, param2);
  } else {
    process.stderr.write(`Unknown action: ${action}\n`);
    process.exit(2);
  }
})();
