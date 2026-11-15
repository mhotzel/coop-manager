<script setup lang="ts">
import { currentUser } from '../auth'
</script>

<template>
  <div class="card">
    <div class="card-header">Willkommen</div>
    <div class="card-content">
      <p>Hallo {{ currentUser?.full_name }}, hier entsteht die Mitgliederverwaltung der Unser Dorfladen Schlichten eG.</p>
    </div>
  </div>
</template>
