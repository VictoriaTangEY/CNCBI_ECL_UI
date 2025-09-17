<template>
  <div style="display: flex; min-height: 100vh; margin-top: 95px;">
  <!-- 左侧导航栏 -->
  <aside style="width: 280px; background-color: #f5f5f5; padding: 30px 20px;">
  <h3 style="font-weight: bold; font-size: 22px; margin-bottom: 24px;">Audit Trail</h3>
  <ul style="list-style: none; padding-left: 0;">
  <li @click="currentTab = 'admin'" :style="{ cursor: 'pointer', color: currentTab === 'admin' ? '#ff612c' : '#333', fontWeight: currentTab === 'admin' ? '600' : 'normal', marginBottom: '10px', fontSize: '20px' }">▸ Admin Logs</li>
  <li @click="currentTab = 'system'" :style="{ cursor: 'pointer', color: currentTab === 'system' ? '#ff612c' : '#333', fontWeight: currentTab === 'system' ? '600' : 'normal', fontSize: '20px' }">▸ System Logs</li>
  </ul>
  </aside>
  <!-- 主体内容 -->
  <main style="flex-grow: 1; padding: 40px;">
  <!-- 面包屑导航 -->
  <nav aria-label="breadcrumb" class="breadcrumb-nav">
  <ol class="breadcrumb-list">
  <li><svg style="width:16px; height:16px; fill:#666; vertical-align:middle;" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg> Home</li>
  <li>Audit Trail</li>
  <li>{{ currentTab === 'admin' ? 'Admin Logs' : 'System Logs' }}</li>
  </ol>
  </nav>
  <!-- 内容卡片 -->
  <div class="config-outer-box">
  <div class="config-inner-box">
  <h2 class="upload-title">{{ currentTab === 'admin' ? 'Admin Audit Logs' : 'System Audit Logs' }}</h2>
  <p style="color: #888; margin-bottom: 24px;">
              {{ currentTab === 'admin' ? 'Download admin activity reports' : 'Download system operation reports' }}
  </p>
  <!-- 下载卡片区域 -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;">
  <div v-for="(card, idx) in currentCards" :key="idx" style="border: 1px solid #e0e0e0; padding: 24px; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(21,61,119,0.04);">
  <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">{{ card.title }}</h3>
  <p style="font-size: 15px; color: #888; margin-bottom: 16px;">{{ card.description }}</p>
  <button class="step-btn" style="background: #2563eb; color: #fff; font-size: 15px;" @click="download(card.title, card.formats[0])">Download</button>
  </div>
  </div>
  </div>
  </div>
  </main>
  </div>
  </template>
  <script setup>
  import { ref, computed } from 'vue'
  import axios from 'axios'
  const currentTab = ref('admin')
  const adminCards = [
    {
      title: 'User & Role Updates',
      description: 'User and role modification history',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'user_role_updates'
    },
    {
      title: 'User Access',
      description: 'Login/logout activity records',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'user_access'
    },
    {
      title: 'Download Activity',
      description: 'File download history',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'download_activity'
    },
    {
      title: 'All Admin Logs',
      description: 'Complete admin activity bundle',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'all_admin_logs'
    }
  ]
  const systemCards = [
    {
      title: 'ECL Job Execution',
      description: 'Batch job execution history',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'ecl_job_execution'
    },
    {
      title: 'ECL Result Confirmation',
      description: 'Result approval records',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'ecl_result_confirmation'
    },
    {
      title: 'Parameter Updates',
      description: 'System parameter change history',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'parameter_updates'
    },
    {
      title: 'Data Sanity Reports',
      description: 'Data quality check results',
      formats: ['LOG'],
      buttonText: 'Download',
      logType: 'data_sanity_reports'
    }
  ]
  const currentCards = computed(() => currentTab.value === 'admin' ? adminCards : systemCards)
  async function download(reportTitle, format) {
    try {
      // Find the card that matches the report title
      const card = currentCards.value.find(c => c.title === reportTitle)
      if (!card || !card.logType) {
        console.error('Log type not found for:', reportTitle)
        return
      }
      // Call the backend API to download the audit log
      const response = await axios.get(`/api/download_audit_log/${card.logType}`, {
        responseType: 'blob'
      })
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${card.logType}.txt`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      console.log(`Downloaded ${reportTitle} as .txt`)
    } catch (error) {
      console.error('Download failed:', error)
      alert('Download failed. Please try again.')
    }
  }
  </script>
  <style scoped>
  .breadcrumb-nav {
    margin-bottom: 18px;
  }
  .breadcrumb-list {
    display: flex;
    align-items: center;
    gap: 8px;
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 18px;
    color: #555;
  }
  .breadcrumb-list li:not(:last-child)::after {
    content: '>';
    margin: 0 6px;
    color: #bbb;
  }
  .config-outer-box {
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 2px 12px rgba(21,61,119,0.06);
    padding: 0 0 30px 0;
    margin-bottom: 40px;
    position: relative;
  }
  .config-inner-box {
    padding: 30px 30px 0 30px;
  }
  .upload-title {
    font-size: 18px;
    font-weight: bold;
    color: #153D77;
    margin-bottom: 24px;
  }
  .select-input-full {
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid #ddd;
    font-size: 14px;
    width: 100%;
    box-sizing: border-box;
  }
  .step-btn {
    padding: 10px 28px;
    background: #f0f0f0;
    color: #333;
    border-radius: 20px;
    border: none;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    transition: background-color 0.3s;
    margin: 0 5px;
  }
  .step-btn:hover {
    background: #e0e0e0;
  }
  .step-btn:disabled {
    background: #eee;
    color: #bbb;
    cursor: not-allowed;
  }
  </style>