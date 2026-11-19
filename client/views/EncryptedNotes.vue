<template>
  <div class="mx-auto w-full max-w-3xl">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl">Protected notes</h1>
      <RouterLink v-if="globalStore.config.encryptionEnabled" :to="{ name: 'encryptedNote', params: { id: 'new' } }">
        <CustomButton label="New protected note" />
      </RouterLink>
    </div>
    <p class="mb-4 text-sm text-theme-text-muted">
      Titles remain encrypted. Unlock a note to see its content and title.
    </p>
    <p v-if="errorMessage" role="alert" class="text-theme-danger">{{ errorMessage }}</p>
    <p v-else-if="!notes.length">No protected notes.</p>
    <ul class="space-y-2">
      <li v-for="note in notes" :key="note.id">
        <RouterLink
          class="block rounded border border-theme-border p-3 hover:bg-theme-background-elevated"
          :to="{ name: 'encryptedNote', params: { id: note.id } }"
        >
          <span aria-hidden="true">🔒</span> {{ note.id }}
        </RouterLink>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { listEncryptedNotes } from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import { useGlobalStore } from "../globalStore.js";

const globalStore = useGlobalStore();
const notes = ref([]);
const errorMessage = ref("");

onMounted(async () => {
  try {
    notes.value = await listEncryptedNotes();
  } catch {
    errorMessage.value = "Unable to load the encrypted notes list.";
  }
});
</script>
