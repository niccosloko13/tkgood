const fs=require('node:fs'),vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');
const {document,window}=domFixture(fs.readFileSync('tests/fixtures/tiktok-comments-live.html','utf8'),'https://www.tiktok.com/@maker/video/123');
const context=vm.createContext({URL,document,window,setTimeout(fn){queueMicrotask(fn);}});
vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'),context);
vm.runInContext(fs.readFileSync('extension/comments.js','utf8'),context);
vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context)
  .then(result=>process.stdout.write(JSON.stringify(result)));
