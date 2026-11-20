import * as constants from "./constants.js";

import { Note, SearchResult } from "./classes.js";

import axios from "axios";
import { getStoredToken } from "./tokenStorage.js";
import { getToastOptions } from "./helpers.js";
import router from "./router.js";

const api = axios.create();

api.interceptors.request.use(
  // If the request is not for the token endpoint, add the token to the headers.
  function (config) {
    if (config.url !== "api/token") {
      const token = getStoredToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  function (error) {
    return Promise.reject(error);
  },
);

export function apiErrorHandler(error, toast) {
  if (error.response?.status === 401) {
    const redirectPath = router.currentRoute.value.fullPath;
    router.push({
      name: "login",
      query: { [constants.params.redirect]: redirectPath },
    });
  } else {
    console.error(error);
    toast.add(
      getToastOptions(
        "Unknown error communicating with the server. Please try again.",
        "Unknown Error",
        "error",
      ),
    );
  }
}

export async function getConfig() {
  try {
    const response = await api.get("api/config");
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getToken(username, password, totp) {
  try {
    const response = await api.post("api/token", {
      username: username,
      password: totp ? password + totp : password,
    });
    return response.data.access_token;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function authCheck() {
  try {
    const response = await api.get("api/auth-check");
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getNotes(term, sort, order, limit) {
  try {
    const response = await api.get("api/search", {
      params: {
        term: term,
        sort: sort,
        order: order,
        limit: limit,
      },
    });
    return response.data.map((note) => new SearchResult(note));
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function createNote(title, content, expiration = null) {
  try {
    const response = await api.post("api/notes", {
      title: title,
      content: content,
      expiration,
    });
    return new Note(response.data);
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getNote(title) {
  try {
    const response = await api.get(`api/notes/${encodeURIComponent(title)}`);
    return new Note(response.data);
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function updateNote(title, newTitle, newContent) {
  try {
    const response = await api.patch(`api/notes/${encodeURIComponent(title)}`, {
      newTitle: newTitle,
      newContent: newContent,
    });
    return new Note(response.data);
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function deleteNote(title) {
  try {
    await api.delete(`api/notes/${encodeURIComponent(title)}`);
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getTags() {
  try {
    const response = await api.get("api/tags");
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function createAttachment(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post("api/attachments", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}


// Publication management requires the existing owner authentication.
export async function getPublication(title) {
  const response = await api.get("api/notes/" + encodeURIComponent(title) + "/publication");
  return response.data;
}

export async function savePublication(title, settings) {
  const response = await api.put("api/notes/" + encodeURIComponent(title) + "/publication", settings);
  return response.data;
}

export async function removePublication(title) {
  await api.delete("api/notes/" + encodeURIComponent(title) + "/publication");
}

// Anonymous endpoints use the same API host but require no credentials.
export async function getPublicNote(slug) {
  const response = await api.get("api/public/notes/" + encodeURIComponent(slug));
  return response.data;
}

export async function updatePublicNote(slug, content, revision) {
  const response = await api.patch("api/public/notes/" + encodeURIComponent(slug), {
    newContent: content,
    revision: revision,
  });
  return response.data;
}


// Protected note transport carries opaque ciphertext. No password is sent.
export async function listEncryptedNotes() {
  const response = await api.get("api/encrypted-notes");
  return response.data;
}

export async function fetchEncryptedNote(noteId, slug = null) {
  const path = slug
    ? "api/public/encrypted-notes/" + encodeURIComponent(slug)
    : "api/encrypted-notes/" + encodeURIComponent(noteId);
  const response = await api.get(path, { responseType: "text" });
  return {
    ciphertext: response.data,
    noteId: response.headers["x-note-id"] || noteId,
    revision: response.headers["x-revision"],
    permission: response.headers["x-edit-permission"] || "edit",
    expiration: {
      mode: response.headers["x-expiration-mode"] || "none",
      policy: response.headers["x-expiration-policy"] || "none",
      expiresAt: Number(response.headers["x-expires-at"]) || null,
    },
  };
}

export async function saveEncryptedNote(noteId, ciphertext, revision, slug = null, expiration = null, verifier = null) {
  const path = slug
    ? "api/public/encrypted-notes/" + encodeURIComponent(slug)
    : "api/encrypted-notes/" + encodeURIComponent(noteId);
  const response = await api.put(path, ciphertext, {
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Revision": revision,
      ...(expiration !== null ? { "X-Expiration": expiration } : {}),
      ...(verifier ? { "X-View-Verifier": verifier } : {}),
    },
  });
  return response.data;
}

export async function protectPlainNote(title, noteId, ciphertext, lastModified, verifier = null) {
  const response = await api.post(
    "api/encrypted-notes/protect/" + encodeURIComponent(title) + "/" + noteId,
    ciphertext,
    {
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Source-Modified": String(lastModified),
        ...(verifier ? { "X-View-Verifier": verifier } : {}),
      },
    },
  );
  return response.data;
}

export async function deleteEncryptedNote(noteId) {
  await api.delete("api/encrypted-notes/" + encodeURIComponent(noteId));
}

export async function getEncryptedPublication(noteId) {
  const response = await api.get("api/encrypted-notes/" + noteId + "/publication");
  return response.data;
}

export async function saveEncryptedPublication(noteId, settings) {
  const response = await api.put("api/encrypted-notes/" + noteId + "/publication", settings);
  return response.data;
}

export async function removeEncryptedPublication(noteId) {
  await api.delete("api/encrypted-notes/" + noteId + "/publication");
}


// Lifecycle API exposes only policy metadata and opaque note identifiers.
export async function listExpiringNotes() {
  const response = await api.get("api/expiring-notes");
  return response.data;
}

export async function getNoteExpiration(kind, noteId) {
  const path = kind === "encrypted"
    ? "api/encrypted-notes/" + encodeURIComponent(noteId)
    : "api/notes/" + encodeURIComponent(noteId);
  const response = await api.get(path + "/expiration");
  return response.data;
}

export async function setNoteExpiration(kind, noteId, policy, verifier = null) {
  const path = kind === "encrypted"
    ? "api/encrypted-notes/" + encodeURIComponent(noteId)
    : "api/notes/" + encodeURIComponent(noteId);
  const response = await api.put(path + "/expiration", { policy, verifier });
  return response.data;
}

export async function consumeEncryptedView(noteId, proof, slug = null) {
  const path = slug
    ? "api/public/encrypted-notes/" + encodeURIComponent(slug) + "/view"
    : "api/encrypted-notes/" + encodeURIComponent(noteId) + "/view";
  const response = await api.post(path, { proof });
  return response.data;
}
