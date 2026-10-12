const {test} = require('node:test');
const assert = require('node:assert/strict');
const {extractMediaId, fetchMedia, selectDownload} = require('../instagram_api_bridge');

test('shortcode is decoded without losing integer precision', () => {
  assert.equal(extractMediaId('https://instagram.com/reel/BA/?utm_source=test'), '64');
  assert.match(extractMediaId('https://www.instagram.com/reel/DdxbmN3SHE6/'), /^\d+$/);
  assert.equal(extractMediaId('https://instagram.com/stories/user.name/123456789/'), '123456789');
  assert.throws(() => extractMediaId('https://evil.example/reel/BA/'));
});

test('media info uses the installed API and unwraps items', async () => {
  const media = {id: '64'};
  const ig = {media: {info: async id => {
    assert.equal(id, '64');
    return {items: [media]};
  }}};
  assert.equal(await fetchMedia(ig, 'https://instagram.com/p/BA/'), media);
});

test('video versions take priority over cover images', () => {
  assert.deepEqual(selectDownload({
    video_versions: [{url: 'video-low', width: 100, height: 100},
                     {url: 'video-high', width: 200, height: 200}],
    image_versions2: {candidates: [{url: 'cover'}]},
  }), {url: 'video-high', mediaType: 'video'});
});

test('carousel uses its first item, not the parent cover', () => {
  assert.deepEqual(selectDownload({
    image_versions2: {candidates: [{url: 'cover'}]},
    carousel_media: [{video_versions: [{url: 'video'}]}],
  }), {url: 'video', mediaType: 'video'});
  assert.deepEqual(selectDownload({image_versions2: {candidates: [{url: 'photo'}]}}),
    {url: 'photo', mediaType: 'photo'});
});
