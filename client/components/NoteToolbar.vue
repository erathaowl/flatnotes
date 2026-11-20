<template>
  <div class="flex flex-wrap items-center gap-1 print:hidden sm:gap-2">
    <CustomButton v-if="encrypted" :iconPath="mdilLock" label="Lock" @click="$emit('lock')" />
    <CustomButton
      v-if="showShare"
      :iconPath="mdilLink"
      label="Share"
      :style="shareActive ? 'active' : 'subtle'"
      :disabled="busy || !canModify || consumed"
      @click="$emit('share')"
    />
    <CustomButton
      v-if="showExpiration"
      :iconPath="mdilClock"
      label="Expiration"
      :style="expirationActive ? 'active' : 'subtle'"
      :disabled="busy || !canModify || consumed"
      @click="$emit('expiration')"
    />
    <CustomButton
      v-if="showProtect"
      :iconPath="mdilLock"
      label="Protect"
      :disabled="busy"
      title="Encrypt this note in your browser"
      @click="$emit('protect')"
    />
    <CustomButton
      :iconPath="mdilDownload"
      label="Export Markdown"
      :disabled="busy"
      @click="$emit('export')"
    />
    <CustomButton
      v-if="canModify && !consumed"
      :iconPath="mdilDelete"
      label="Delete"
      style="danger"
      :disabled="busy"
      @click="$emit('delete')"
    />
    <CustomButton
      v-if="canModify && editing && encrypted"
      :iconPath="mdilPaperclip"
      label="Attach file"
      :disabled="busy"
      @click="$emit('attach')"
    />
    <CustomButton
      v-if="canModify && editing"
      :iconPath="mdilCancel"
      label="Cancel"
      :disabled="busy"
      @click="$emit('cancel')"
    />
    <CustomButton
      v-if="canModify && editing"
      :iconPath="mdilContentSave"
      label="Save"
      :disabled="busy"
      @click="$emit('save')"
    />
    <Toggle
      v-if="canModify"
      label="Edit"
      :isOn="editing"
      :disabled="busy"
      @click="$emit('toggle-edit')"
    />
  </div>
</template>

<script setup>
import {
  mdilCancel, mdilClock, mdilContentSave, mdilDelete,
  mdilDownload, mdilLink, mdilLock, mdilPaperclip,
} from "@mdi/light-js";

import CustomButton from "./CustomButton.vue";
import Toggle from "./Toggle.vue";

defineProps({
  encrypted: { type: Boolean, default: false },
  editing: { type: Boolean, default: false },
  isNew: { type: Boolean, default: false },
  canModify: { type: Boolean, default: true },
  consumed: { type: Boolean, default: false },
  showShare: { type: Boolean, default: false },
  showExpiration: { type: Boolean, default: false },
  showProtect: { type: Boolean, default: false },
  shareActive: { type: Boolean, default: false },
  expirationActive: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
});

defineEmits([
  "lock", "share", "expiration", "protect", "export",
  "delete", "attach", "cancel", "save", "toggle-edit",
]);
</script>
