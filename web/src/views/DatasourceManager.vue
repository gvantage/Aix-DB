<script lang="ts" setup>
import { useDialog } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import DatasourceForm from '@/components/Datasource/DatasourceForm.vue'

const dialog = useDialog()
const router = useRouter()

const loading = ref(false)
const datasourceList = ref<any[]>([])
const keywords = ref('')
const showForm = ref(false)
const currentDatasource = ref<any>(null)

// 获取数据源列表
const fetchDatasourceList = async () => {
  loading.value = true
  try {
    const url = new URL(`${location.origin}/sanic/datasource/list`)
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      datasourceList.value = result.data || []
    } else {
      window.$ModalMessage.error(result.msg || '获取数据源列表失败')
    }
  } catch (error) {
    console.error('获取数据源列表失败:', error)
    window.$ModalMessage.error('获取数据源列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索过滤
const filteredList = computed(() => {
  if (!keywords.value) {
    return datasourceList.value
  }
  return datasourceList.value.filter((item) =>
    item.name.toLowerCase().includes(keywords.value.toLowerCase()),
  )
})

// 添加数据源
const handleAdd = () => {
  currentDatasource.value = null
  showForm.value = true
}

// 编辑数据源
const handleEdit = async (item: any) => {
  try {
    // 获取完整的数据源信息
    const url = new URL(`${location.origin}/sanic/datasource/get/${item.id}`)
    const response = await fetch(url, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      currentDatasource.value = result.data
      showForm.value = true
    } else {
      window.$ModalMessage.error(result.msg || '获取数据源信息失败')
    }
  } catch (error) {
    console.error('获取数据源信息失败:', error)
    window.$ModalMessage.error('获取数据源信息失败')
  }
}

// 删除数据源
const handleDelete = (item: any) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除数据源"${item.name}"吗？此操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const url = new URL(`${location.origin}/sanic/datasource/delete/${item.id}`)
        const response = await fetch(url, {
          method: 'POST',
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const result = await response.json()
        if (result.code === 200) {
          window.$ModalMessage.success('删除成功')
          fetchDatasourceList()
        } else {
          window.$ModalMessage.error(result.msg || '删除失败')
        }
      } catch (error) {
        console.error('删除数据源失败:', error)
        window.$ModalMessage.error('删除数据源失败')
      }
    },
  })
}

// 表单保存成功回调
const handleFormSuccess = () => {
  fetchDatasourceList()
}

// 跳转到数据表页面
const handleViewTables = (item: any) => {
  router.push(`/datasource/table/${item.id}/${encodeURIComponent(item.name)}`)
}

onMounted(() => {
  fetchDatasourceList()
})
</script>

<template>
  <div class="datasource-manager">
    <div class="header">
      <h2>数据源管理</h2>
      <div class="actions">
        <n-input
          v-model:value="keywords"
          placeholder="搜索数据源"
          clearable
          style="width: 240px; margin-right: 12px"
        />
        <n-button
          type="primary"
          @click="handleAdd"
        >
          新建数据源
        </n-button>
      </div>
    </div>

    <n-spin :show="loading">
      <div
        v-if="filteredList.length > 0"
        class="content"
      >
        <n-grid
          :cols="4"
          :x-gap="16"
          :y-gap="16"
        >
          <n-grid-item
            v-for="item in filteredList"
            :key="item.id"
          >
            <n-card
              hoverable
              class="datasource-card"
              @click="handleViewTables(item)"
            >
              <template #header>
                <div class="card-header">
                  <img
                    src="@/assets/svg/mysql-icon.svg"
                    alt="MySQL"
                    class="datasource-icon"
                  >
                  <span>{{ item.name }}</span>
                </div>
              </template>
              <div class="card-content">
                <p class="description">
                  {{ item.description || '暂无描述' }}
                </p>
                <div class="meta">
                  <span class="type">{{ item.type_name || item.type }}</span>
                  <span
                    class="status"
                    :class="item.status === 'Success' ? 'success' : 'failed'"
                  >
                    {{ item.status === 'Success' ? '正常' : '异常' }}
                  </span>
                </div>
                <div
                  v-if="item.num"
                  class="table-count"
                >
                  表数量: {{ item.num }}
                </div>

                <!-- 操作按钮：放置于右下角并默认隐藏 -->
                <div class="actions-overlay">
                  <div class="action-buttons">
                    <n-button
                      text
                      type="default"
                      @click.stop="handleEdit(item)"
                    >
                      编辑
                    </n-button>
                    <n-button
                      text
                      type="error"
                      @click.stop="handleDelete(item)"
                    >
                      删除
                    </n-button>
                  </div>
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
      </div>
      <div
        v-else
        class="empty-container"
      >
        <n-empty description="暂无数据源" />
      </div>
    </n-spin>

    <!-- 数据源表单对话框 -->
    <DatasourceForm
      v-model:show="showForm"
      :datasource="currentDatasource"
      @success="handleFormSuccess"
    />
  </div>
</template>

<style lang="scss" scoped>
.datasource-manager {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
    }

    .actions {
      display: flex;
      align-items: center;
    }
  }

  .content {
    flex: 1;
    overflow-y: auto;
  }

  .empty-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 400px;
  }

  .datasource-card {
    cursor: pointer;
    background: rgba(240, 249, 255, 0.6);
    transition: background 0.3s ease;

    &:hover {
      background: rgba(240, 249, 255, 0.9);
    }

    :deep(.n-card__content) {
      cursor: pointer;
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;

      .datasource-icon {
        width: 20px;
        height: 20px;
        flex-shrink: 0;
      }
    }
  }

  .card-content {
    position: relative;
    cursor: pointer;

    .description {
      margin: 8px 0;
      color: #666;
      font-size: 14px;
    }

    .meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 12px;

      .type {
        font-size: 12px;
        color: #999;
      }

      .status {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;

        &.success {
          background: #f0f9ff;
          color: #1890ff;
        }

        &.failed {
          background: #fff1f0;
          color: #ff4d4f;
        }
      }
    }

    .table-count {
      margin-top: 8px;
      font-size: 12px;
      color: #999;
    }

    /* 右下角浮动操作按钮 */

    .actions-overlay {
      position: absolute;
      bottom: 8px;
      right: 8px;
      opacity: 0;
      transition: opacity 0.3s ease-in-out;
      pointer-events: none; // 默认不响应点击事件

      .action-buttons {
        display: flex;
        gap: 8px;
      }
    }

    &:hover {

      .actions-overlay {
        opacity: 1;
        pointer-events: all; // 悬停时启用点击
      }
    }
  }
}
</style>
