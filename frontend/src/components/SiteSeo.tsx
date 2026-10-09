import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { usePublicSite } from "../lib/usePublicSite";
import type { SeoPageKey, SiteSeoSettings } from "../types";

function upsertMeta(attr: "name" | "property", key: string, content: string) {
  if (!content) return;
  let el = document.head.querySelector(`meta[${attr}="${key}"]`) as HTMLMetaElement | null;
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.content = content;
}

function upsertLink(rel: string, href: string) {
  if (!href) return;
  let el = document.head.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;
  if (!el) {
    el = document.createElement("link");
    el.rel = rel;
    document.head.appendChild(el);
  }
  el.href = href;
}

function resolveCopy(
  seo: SiteSeoSettings,
  page: SeoPageKey,
  landing?: { hero_title: string; hero_subtitle: string },
  overrides?: { title?: string; description?: string },
) {
  const pageMeta = seo.pages[page];
  let title = (overrides?.title || pageMeta?.title || "").trim();
  let description = (overrides?.description || pageMeta?.description || "").trim();
  if (page === "home" && !title && landing?.hero_title) title = landing.hero_title;
  if (page === "home" && !description && landing?.hero_subtitle) description = landing.hero_subtitle;
  if (!title) title = seo.default_title;
  else if (seo.title_suffix && !title.endsWith(seo.title_suffix.trim())) {
    title = `${title}${seo.title_suffix}`;
  }
  if (!description) description = seo.default_description;
  return { title, description, noindex: Boolean(pageMeta?.noindex) };
}

export function SiteSeo({
  page = "home",
  title,
  description,
  noindex,
}: {
  page?: SeoPageKey;
  title?: string;
  description?: string;
  noindex?: boolean;
}) {
  const { data: site } = usePublicSite();
  const { pathname } = useLocation();

  useEffect(() => {
    const seo = site?.seo;
    if (!seo) return;
    const base = seo.site_url.replace(/\/$/, "");
    const canonical = `${base}${pathname === "/" ? "/" : pathname}`;
    const copy = resolveCopy(seo, page, site?.landing, { title, description });
    const blockIndex = noindex ?? copy.noindex ?? !seo.robots_index;

    document.title = copy.title;
    document.documentElement.lang = "en";

    upsertMeta("name", "description", copy.description);
    upsertMeta("name", "keywords", seo.default_keywords);
    upsertMeta("name", "robots", blockIndex ? "noindex, nofollow" : "index, follow");

    upsertMeta("property", "og:type", "website");
    upsertMeta("property", "og:site_name", site?.branding.app_name ?? "ApplyXAI");
    upsertMeta("property", "og:title", copy.title);
    upsertMeta("property", "og:description", copy.description);
    upsertMeta("property", "og:url", canonical);
    upsertMeta("property", "og:image", seo.og_image_url);

    upsertMeta("name", "twitter:card", seo.twitter_card);
    upsertMeta("name", "twitter:title", copy.title);
    upsertMeta("name", "twitter:description", copy.description);
    upsertMeta("name", "twitter:image", seo.og_image_url);
    if (site?.branding.social_links?.twitter) {
      const handle = site.branding.social_links.twitter.replace(/^@/, "");
      if (handle) upsertMeta("name", "twitter:site", `@${handle}`);
    }

    upsertLink("canonical", canonical);

    if (seo.google_site_verification) {
      upsertMeta("name", "google-site-verification", seo.google_site_verification);
    }
    if (seo.bing_site_verification) {
      upsertMeta("name", "msvalidate.01", seo.bing_site_verification);
    }

    if (page === "home" && !blockIndex) {
      const orgId = "applyxai-jsonld-org";
      let script = document.getElementById(orgId) as HTMLScriptElement | null;
      if (!script) {
        script = document.createElement("script");
        script.id = orgId;
        script.type = "application/ld+json";
        document.head.appendChild(script);
      }
      script.textContent = JSON.stringify({
        "@context": "https://schema.org",
        "@type": "Organization",
        name: site?.branding.app_name ?? "ApplyXAI",
        url: base,
        logo: seo.og_image_url,
        email: site?.branding.contact_email,
      });
    }
  }, [site, page, title, description, noindex, pathname]);

  return null;
}

/** Map public routes to CMS SEO page keys. */
export function seoPageForPath(pathname: string): SeoPageKey {
  if (pathname === "/") return "home";
  if (pathname === "/login") return "login";
  if (pathname.startsWith("/register")) return "register";
  if (pathname === "/privacy") return "privacy";
  if (pathname === "/terms") return "terms";
  if (pathname === "/refund-policy") return "refund";
  return "home";
}
