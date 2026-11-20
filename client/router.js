import * as constants from "./constants.js";

import { createRouter, createWebHistory } from "vue-router";

import { authCheck } from "./api.js";
import { useGlobalStore } from "./globalStore.js";

const router = createRouter({
  history: createWebHistory(""),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("./views/Home.vue"),
    },
    {
      path: "/login",
      name: "login",
      component: () => import("./views/LogIn.vue"),
      props: (route) => ({ redirect: route.query[constants.params.redirect] }),
    },
    {
      path: "/n/:title",
      name: "note",
      component: () => import("./views/Note.vue"),
      props: true,
    },
    {
      path: "/note/:title",
      redirect: (to) => ({ name: "note", params: { title: to.params.title } }),
    },
    {
      path: "/e/:id",
      name: "encryptedNote",
      component: () => import("./views/EncryptedNote.vue"),
      props: true,
    },
    {
      path: "/expiring",
      name: "expiringNotes",
      component: () => import("./views/ExpiringNotes.vue"),
    },
    {
      path: "/encrypted",
      name: "encryptedNotes",
      component: () => import("./views/EncryptedNotes.vue"),
    },
    {
      path: "/p/:slug",
      name: "publicNote",
      component: () => import("./views/PublicNote.vue"),
      props: true,
      meta: { public: true },
    },
    {
      path: "/new",
      name: "new",
      component: () => import("./views/Note.vue"),
    },
    {
      path: "/search",
      name: "search",
      component: () => import("./views/SearchResults.vue"),
      props: (route) => ({
        searchTerm: route.query[constants.params.searchTerm],
        sortBy: Number(route.query[constants.params.sortBy]) || undefined,
      }),
    },
  ],
});

// Check the user is authenticated on first navigation (unless going to login)
let authChecked = false;
router.beforeEach(async (to) => {
  if (authChecked || to.name === "login" || to.meta.public) {
    return;
  }
  try {
    await authCheck();
    return;
  } catch (error) {
    if (error.response && error.response.status === 401) {
      return {
        name: "login",
        query: { [constants.params.redirect]: to.fullPath },
      };
    }
  } finally {
    authChecked = true;
  }
});

export function updatePageTitle(to) {
  let title = useGlobalStore().config.siteTitle || "flatnotes";
  if (to.name === "publicNote") {
    title = "Shared Note - " + title;
  }
  if (to.name === "encryptedNote") {
    title = "Protected Note - " + title;
  }
  if (to.name === "note") {
    if (to.params.title) {
      title = `${to.params.title} - ${title}`;
    } else {
      title = "New Note - " + title;
    }
  }
  document.title = title;
}

router.afterEach(updatePageTitle);

export default router;
