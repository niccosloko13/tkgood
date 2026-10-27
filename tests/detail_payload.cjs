// Emit the actual isolated detail extractor payload for backend contract tests.
const fs=require('node:fs');
const vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');
const {document,window}=domFixture(fs.readFileSync('tests/fixtures/tiktok-detail-metrics.html','utf8'),'https://www.tiktok.com/@maker/video/123');
document.readyState='complete';
const context=vm.createContext({document,window,URL});
vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'),context);
vm.runInContext(fs.readFileSync('extension/video_detail.js','utf8'),context);
process.stdout.write(JSON.stringify(vm.runInContext('ProductHunterDetail.extractVideoDetail().video_detail',context)));
