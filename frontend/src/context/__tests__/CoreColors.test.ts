import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import postcss from "postcss";
import tailwind from "tailwindcss";
import { expect, it } from "vitest";
// @ts-expect-error JavaScript build configuration has no declaration file.
import config from "../../../tailwind.config.js";
import { THEME_PALETTES } from "../ThemeContext";

const source = readFileSync(new URL("../../index.css", import.meta.url), "utf8");
function tokens(light: boolean) {
  const selector = light ? ":root.light-theme" : ":root";
  const rule = postcss.parse(source).nodes.find(n => n.type === "rule" && n.selector === selector) as postcss.Rule;
  return Object.fromEntries(rule.nodes.filter(n => n.type === "decl").map(n => [(n as postcss.Declaration).prop, (n as postcss.Declaration).value]));
}
function resolve(value: string, vars: Record<string, string>): string {
  return value.replace(/var\((--[\w-]+)(?:,\s*([^)]*))?\)/g, (_, key, fallback) => vars[key] ?? fallback ?? "1");
}
const rgb = (hex: string) => hex.slice(1).match(/../g)!.map(v => parseInt(v, 16));
const luminance = (color: number[]) => color.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
function contrast(a: number[], b: number[]) {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}

it.each([false, true])("produces valid opaque and translucent semantic CSS (light=%s)", async light => {
  const styles = await postcss([tailwind({ ...config, content: [{ raw: "bg-accent bg-gain bg-loss border-surface-border bg-accent/15 bg-gain/20 bg-loss/20 text-accent" }] })]).process("@tailwind utilities;", { from: undefined });
  const style = new JSDOM().window.document.createElement("div").style;
  let checked = 0;
  styles.root.walkDecls(decl => {
    if (!decl.value.includes("var(--") || !/^(background-color|border-color|color)$/.test(decl.prop)) return;
    style.removeProperty(decl.prop);
    style.setProperty(decl.prop, resolve(decl.value, tokens(light)));
    expect(style.getPropertyValue(decl.prop), decl.toString()).not.toBe("");
    checked++;
  });
  expect(checked).toBeGreaterThanOrEqual(8);
});

it.each([false, true])("meets 4.5:1 for core enabled text, tinted badges and filled actions (light=%s)", light => {
  const vars = tokens(light);
  for (const surface of ["--bg-primary", "--bg-surface", "--bg-elevated", "--bg-soft", "--bg-hover-strong"]) {
    for (const ink of ["--text-primary", "--text-muted"]) {
      expect(contrast(rgb(vars[ink]), rgb(vars[surface])), `${ink} / ${surface}`).toBeGreaterThanOrEqual(4.5);
    }
  }
  for (const color of ["accent", "gain", "loss"]) {
    const ink = rgb(vars[`--color-${color}`]);
    for (const alpha of [0, .1, .15, .2]) {
      const bg = rgb(vars["--bg-elevated"]).map((v, i) => ink[i] * alpha + v * (1 - alpha));
      expect(contrast(ink, bg), `${color} / tint ${alpha}`).toBeGreaterThanOrEqual(4.5);
    }
    expect(contrast(rgb(vars["--action-ink"]), ink), `${color} filled`).toBeGreaterThanOrEqual(4.5);
  }
  expect(contrast(rgb(vars["--action-ink"]), rgb(vars["--action-hover"])), "primary hover").toBeGreaterThanOrEqual(4.5);
  const warning = rgb(vars["--color-warn"]);
  for (const alpha of [.1, .2]) {
    const background = rgb(vars["--bg-elevated"]).map((v, i) => warning[i] * alpha + v * (1 - alpha));
    expect(contrast(warning, background), `warning / tint ${alpha}`).toBeGreaterThanOrEqual(4.5);
  }
});

it.each(["dark", "light"] as const)("keeps cold CSS and runtime/chart palette consistent (%s)", theme => {
  const vars = tokens(theme === "light"), palette = THEME_PALETTES[theme];
  for (const [key, value] of Object.entries({ "--bg-primary": palette.background, "--bg-surface": palette.surface,
    "--border-color": palette.surfaceBorder, "--text-primary": palette.text, "--text-muted": palette.textMuted,
    "--color-accent": palette.accent, "--color-gain": palette.bullish, "--color-loss": palette.bearish })) {
    expect(vars[key], key).toBe(value);
  }
});

it("keeps disabled actions distinguishable, excludes disabled hover and preserves visible keyboard focus", () => {
  const css = postcss.parse(source);
  const rule = (selector: string) => css.nodes.find(n => n.type === "rule" && n.selector === selector) as postcss.Rule;
  const value = (selector: string, prop: string) => (rule(selector).nodes.find(n => n.type === "decl" && n.prop === prop) as postcss.Declaration)?.value;
  expect(value(".k-primary:disabled", "opacity")).toBe("0.6");
  expect(value(".k-primary:hover:not(:disabled)", "background-color")).toBe("var(--action-hover)");
  expect(value(".k-btn:focus-visible", "outline")).toContain("2px solid");
  expect(value(".k-btn", "min-height")).toBe("44px");
  expect(value(".k-primary, .k-control, .k-nav-active", "transition-property")).toBe("transform, box-shadow");
});
