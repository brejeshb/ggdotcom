<template>
  <div class="p-4">
    <h1 class="text-2xl font-bold mb-4">Tour History</h1>
    <div v-for="(tour, index) in tours" :key="index" class="mb-6">
      <div @click="toggleDropdown(index)" class="cursor-pointer bg-red-400 text-white p-3 rounded-lg flex justify-between items-center">
        <h2 class="text-lg font-semibold">{{ tour.date }}</h2>
        <span :class="dropdowns[index] ? 'rotate-180' : 'rotate-0'" class="transform transition-transform">
          ▼
        </span>
      </div>
      <div v-show="dropdowns[index]" class="mt-2 bg-white shadow rounded-lg p-4">
        <div v-for="(message, msgIndex) in tour.messages" :key="msgIndex" class="mb-2">
          <div
            :class="[
              'p-2 rounded-lg',
              message.isUser ? 'bg-gray-100 text-gray-800' : 'bg-red-50 text-gray-800',
            ]"
          >
            {{ message.text }}
          </div>
          <img
            v-if="message.image"
            :src="message.image"
            alt="Tour image"
            class="mt-2 max-w-full h-auto rounded shadow"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const tours = ref([])
const dropdowns = ref([])

const toggleDropdown = (index) => {
  dropdowns.value[index] = !dropdowns.value[index]
}

const fetchTourHistory = async () => {
  try {
    const response = await fetch('https://ggdotcom.onrender.com/messages', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('Failed to fetch tour history')
    }

    const messages = await response.json()


    console.log('Response from backend:', messages)

    // Organize messages by date
    const organizedTours = messages.reduce((acc, msg) => {
      const date = new Date(msg.timestamp).toLocaleDateString() 
      if (!acc[date]) {
        acc[date] = []
      }
      acc[date].push({
        text: msg.chatText || '', 
        isUser: msg.userCheck === "true", 
        image: msg.image || null,
      })
      return acc
    }, {})

    tours.value = Object.keys(organizedTours).map((date) => ({
      date,
      messages: organizedTours[date].reverse(),
    }))

    dropdowns.value = tours.value.map(() => false)
  } catch (error) {
    console.error('Error fetching tour history:', error)
  }
}

onMounted(fetchTourHistory)
</script>
