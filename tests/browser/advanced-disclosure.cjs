// Retained advanced-workflow suites deliberately open progressive-disclosure
// ancestors before exercising their existing controls and numerical assertions.
// The normal default workflow is verified independently in refocus.cjs.
module.exports = function disclose(page) {
  const proto = Object.getPrototypeOf(page.locator("body")),
    rawWait = proto.waitFor;
  if (proto.__veusDisclosure) return;
  proto.__veusDisclosure = true;
  const reveal = async (locator) => {
    const advanced = page.locator("#advanced-analysis");
    if (/insights|analysis-panel|analysis-ack/.test(locator._selector || ""))
      await rawWait.call(advanced, { state: "attached" });
    if (await advanced.count()) await advanced.evaluate((e) => (e.open = true));
    await locator
      .evaluate((el) => {
        let n =
          el.tagName === "SUMMARY"
            ? el.parentElement?.parentElement
            : el.parentElement;
        for (; n; n = n.parentElement)
          if (n.tagName === "DETAILS") n.open = true;
      })
      .catch(() => {});
  };
  for (const name of [
    "click",
    "fill",
    "check",
    "uncheck",
    "selectOption",
    "waitFor",
    "focus",
  ]) {
    const run = proto[name];
    if (run)
      proto[name] = async function (...args) {
        await reveal(this);
        return run.apply(this, args);
      };
  }
  for (const name of [
    "click",
    "fill",
    "check",
    "uncheck",
    "selectOption",
    "focus",
  ]) {
    const run = page[name].bind(page);
    page[name] = async (selector, ...args) => {
      await reveal(page.locator(selector));
      return run(selector, ...args);
    };
  }
};
