const fs=require('node:fs');const {domFixture}=require('./dom-fixture.cjs');
const {extractCreatorProfile}=require('../extension/creator_profile.js');
const {document,window}=domFixture(fs.readFileSync('tests/fixtures/tiktok-creator-profile.html','utf8'),'https://www.tiktok.com/@maker');
document.readyState='complete';process.stdout.write(JSON.stringify(extractCreatorProfile(document,window).creator_profile));
