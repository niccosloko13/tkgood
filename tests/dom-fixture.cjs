const {parseHTML} = require('linkedom');
function domFixture(html, url = 'https://www.tiktok.com/search?q=home+gadgets') {
  const {document, window} = parseHTML(html);
  document.location = {href: url};
  window.innerWidth = 1200;
  window.innerHeight = 800;
  window.getComputedStyle = node => ({display: node.style.display || 'block', visibility: node.style.visibility || 'visible', opacity: node.style.opacity || '1', overflowX: node.style.overflowX || 'visible', overflowY: node.style.overflowY || 'visible'});
  // A DOM parser has no layout engine. Explicit viewport geometry is a fixture,
  // not a claim that every DOM node is visible in Chrome.
  window.HTMLElement.prototype.getBoundingClientRect = function () {
    const top = this.closest('[data-fixture-offscreen]') ? 1000 : 20;
    return {left: 10, right: 310, top, bottom: top + 100, width: 300, height: 100};
  };
  return {document, window};
}
module.exports = {domFixture};
