<script setup lang="ts">
import { currentUser } from '../auth'
</script>

<template>
  <div class="card">
    <div class="card-header">Willkommen</div>
    <div class="card-content">
      <p>Hallo {{ currentUser?.full_name }}, willkommen in der Mitgliederverwaltung.</p>
    </div>
  </div>
</template>
