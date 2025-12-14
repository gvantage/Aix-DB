<script lang="ts" setup>
import { NButton, NIcon, NInput, NLayout, NLayoutContent, NLayoutSider, NMessageProvider, NModal, NSpin, NSwitch, NTable, NTabPane, NTabs, useMessage } from 'naive-ui'
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TableRelationship from './TableRelationship.vue'

const router = useRouter()
const route = useRoute()
const message = useMessage()

const dsId = ref<number>(Number.parseInt(route.params.dsId as string))
const dsName = ref<string>(decodeURIComponent(route.params.dsName as string))

const loading = ref(false)
const initLoading = ref(false)
const searchValue = ref('')
const tableList = ref<any[]>([])
const currentTable = ref<any>({})
const fieldList = ref<any[]>([])
const previewData = ref<any>({ data: [], fields: [] })
const activeName = ref('schema')
const tableDialog = ref(false)
const fieldDialog = ref(false)
const tableComment = ref('')
const fieldComment = ref('')
const currentField = ref<any>({})
const activeRelationship = ref(false)
const relationshipRef = ref<any>(null)
const isDrag = ref(false)

// 搜索过滤
const tableListWithSearch = computed(() => {
  if (!searchValue.value) {
    return tableList.value
  }
  return tableList.value.filter((item) => {
    const name = item.table_name || item.tableName || ''
    return name.toLowerCase().includes(searchValue.value.toLowerCase())
  })
})

// 获取数据源表列表
const fetchTableList = async () => {
  initLoading.value = true
  try {
    const url = new URL(`${location.origin}/sanic/datasource/tableList/${dsId.value}`)
    const response = await fetch(url, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      tableList.value = result.data || []
    } else {
      message.error(result.msg || '获取表列表失败')
    }
  } catch (error) {
    console.error('获取表列表失败:', error)
    message.error('获取表列表失败')
  } finally {
    initLoading.value = false
  }
}

// 点击表
const clickTable = async (table: any) => {
  if (activeRelationship.value) {
    return
  }
  loading.value = true
  currentTable.value = table
  fieldList.value = []
  previewData.value = { data: [], fields: [] }

  try {
    // 获取字段列表
    const url = new URL(`${location.origin}/sanic/datasource/fieldList/${table.id}`)
    const response = await fetch(url, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      fieldList.value = result.data || []

      // 获取预览数据
      await fetchPreviewData()
    } else {
      message.error(result.msg || '获取字段列表失败')
    }
  } catch (error) {
    console.error('获取字段列表失败:', error)
    message.error('获取字段列表失败')
  } finally {
    loading.value = false
  }
}

// 获取预览数据
const fetchPreviewData = async () => {
  try {
    const buildData = {
      table: currentTable.value,
      fields: fieldList.value,
    }

    const url = new URL(`${location.origin}/sanic/datasource/previewData/${dsId.value}`)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(buildData),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      previewData.value = result.data || { data: [], fields: [] }
    }
  } catch (error) {
    console.error('获取预览数据失败:', error)
  }
}

// 编辑表注释
const editTable = () => {
  tableComment.value = currentTable.value.custom_comment || ''
  tableDialog.value = true
}

// 保存表注释
const saveTable = async () => {
  try {
    const url = new URL(`${location.origin}/sanic/datasource/saveTable`)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...currentTable.value,
        custom_comment: tableComment.value,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      currentTable.value.custom_comment = tableComment.value
      tableDialog.value = false
      message.success('保存成功')
    } else {
      message.error(result.msg || '保存失败')
    }
  } catch (error) {
    console.error('保存表注释失败:', error)
    message.error('保存表注释失败')
  }
}

// 编辑字段注释
const editField = (row: any) => {
  currentField.value = row
  fieldComment.value = row.custom_comment || ''
  fieldDialog.value = true
}

// 保存字段注释
const saveField = async () => {
  try {
    const url = new URL(`${location.origin}/sanic/datasource/saveField`)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...currentField.value,
        custom_comment: fieldComment.value,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      const index = fieldList.value.findIndex((f) => f.id === currentField.value.id)
      if (index !== -1) {
        fieldList.value[index].custom_comment = fieldComment.value
      }
      fieldDialog.value = false
      message.success('保存成功')
    } else {
      message.error(result.msg || '保存失败')
    }
  } catch (error) {
    console.error('保存字段注释失败:', error)
    message.error('保存字段注释失败')
  }
}

// 切换字段状态
const changeStatus = async (row: any) => {
  try {
    const url = new URL(`${location.origin}/sanic/datasource/saveField`)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(row),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      message.success('保存成功')
    } else {
      message.error(result.msg || '保存失败')
    }
  } catch (error) {
    console.error('保存字段状态失败:', error)
    message.error('保存字段状态失败')
  }
}

// 切换标签页
const handleTabChange = (name: string) => {
  if (name === 'preview' && previewData.value.data.length === 0) {
    fetchPreviewData()
  }
}

// 返回
const back = () => {
  router.back()
}

// 切换表关系维护
const handleRelationship = async () => {
  activeRelationship.value = !activeRelationship.value
  if (!activeRelationship.value) {
    currentTable.value = {}
    fieldList.value = []
  } else {
    await nextTick()
    if (relationshipRef.value?.loadRelation) {
      relationshipRef.value.loadRelation()
    }
  }
}

// 处理拖拽放置
const handleDrop = (e: DragEvent) => {
  const tableData = e.dataTransfer?.getData('table')
  if (tableData && relationshipRef.value) {
    try {
      const table = JSON.parse(tableData)
      relationshipRef.value.clickTable(table)
    } catch (error) {
      console.error('解析表数据失败:', error)
    }
  }
}

onMounted(() => {
  fetchTableList()
})
</script>

<template>
  <n-message-provider>
    <div class="table-list-layout">
      <n-layout
        has-sider
        style="height: 100vh"
      >
        <n-layout-sider
          :width="280"
          :collapsed-width="0"
          collapse-mode="width"
          bordered
          content-style="padding: 16px; display: flex; flex-direction: column; background-color: #fafafa;"
        >
          <div class="breadcrumb">
            <span
              class="breadcrumb-item"
              @click="back"
            >数据源</span>
            <span class="breadcrumb-separator">></span>
            <span class="breadcrumb-item active">{{ dsName }}</span>
          </div>
          <n-input
            v-model:value="searchValue"
            placeholder="搜索"
            clearable
            class="search-input"
          >
            <template #prefix>
              <span style="color: #999">Q</span>
            </template>
          </n-input>
          <div class="list-content">
            <n-spin :show="initLoading">
              <div
                v-if="tableListWithSearch.length > 0"
                class="table-list"
              >
                <div
                  v-for="item in tableListWithSearch"
                  :key="item.id"
                  class="list-item"
                  :class="{ active: currentTable.id === item.id && !activeRelationship }"
                  :draggable="activeRelationship"
                  @click="activeRelationship ? null : clickTable(item)"
                  @dragstart="(e) => { if (!e.dataTransfer) return; isDrag = true; e.dataTransfer.setData('table', JSON.stringify(item)) }"
                  @dragend="() => { isDrag = false }"
                >
                  <span class="table-icon">
                    <img
                      src="@/assets/images/table-icon.png"
                      alt="表格图标"
                      class="table-icon-img"
                    >
                  </span>
                  <span class="table-name">{{ item.table_name || item.tableName || '-' }}</span>
                </div>
              </div>
              <div
                v-else
                class="empty"
              >
                暂无数据表
              </div>
            </n-spin>
          </div>
          <div class="table-relationship">
            <n-button
              quaternary
              icon-placement="left"
              strong
              :style="{
                'width': `180px`,
                'height': `38px`,
                'margin-left': `20px`,
                'margin-bottom': `10px`,
                'align-self': `center`,
                'text-align': `center`,
                'font-family': `-apple-system, BlinkMacSystemFont,
                'Segoe UI', Roboto, 'Helvetica Neue', Arial,sans-serif`,
                'font-size': `14px`,
              }"
              @click="handleRelationship"
            >
              <template #icon>
                <n-icon>
                  <img
                    src="@/assets/svg/table-relationship.svg"
                    alt="表格图标"
                    style="width: 18px; height: 18px;"
                  >
                </n-icon>
              </template>
              表关系管理
            </n-button>
          </div>
        </n-layout-sider>

        <n-layout-content
          :style="{
            'display': 'flex',
            'flex-direction': 'column',
            'background-color': '#fff',
          }"
        >
          <div
            v-if="activeRelationship"
            class="relationship-content"
            @drop.prevent="handleDrop"
            @dragover.prevent
          >
            <TableRelationship
              ref="relationshipRef"
              :ds-id="dsId"
              :dragging="isDrag"
            />
          </div>

          <div
            v-else-if="currentTable.table_name"
            class="right-side"
          >
            <div class="table-header">
              <div class="table-title">
                <span class="table-name-text">{{ currentTable.table_name }}</span>
              </div>
              <div class="table-comment">
                <span class="comment-label">备注:</span>
                <span class="comment-value">{{ currentTable.custom_comment || '-' }}</span>
                <n-button
                  text
                  size="small"
                  class="edit-btn"
                  @click="editTable"
                >
                  ✏️
                </n-button>
              </div>
            </div>

            <n-tabs
              v-model:value="activeName"
              type="segment"
              class="content-tabs"
              @update:value="handleTabChange"
            >
              <n-tab-pane
                name="schema"
                tab="表结构"
              >
                <n-spin :show="loading">
                  <div class="schema-table-wrapper">
                    <n-table
                      class="data-table"
                      :bordered="false"
                    >
                      <thead>
                        <tr>
                          <th>字段名</th>
                          <th>字段类型</th>
                          <th>字段注释</th>
                          <th>自定义注释</th>
                          <th>状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="row in fieldList"
                          :key="row.id"
                        >
                          <td>{{ row.field_name || row.fieldName }}</td>
                          <td>{{ row.field_type || row.fieldType }}</td>
                          <td>{{ row.field_comment || row.fieldComment || '-' }}</td>
                          <td>
                            <div style="display: flex; align-items: center; gap: 8px">
                              <span>{{ row.custom_comment || '-' }}</span>
                              <n-button
                                text
                                size="small"
                                @click="editField(row)"
                              >
                                编辑
                              </n-button>
                            </div>
                          </td>
                          <td>
                            <n-switch
                              :value="row.checked"
                              @update:value="(val) => { row.checked = val; changeStatus(row) }"
                            />
                          </td>
                        </tr>
                      </tbody>
                    </n-table>
                  </div>
                </n-spin>
              </n-tab-pane>
              <n-tab-pane
                name="preview"
                tab="数据预览"
              >
                <div class="preview-info">
                  显示 {{ previewData.data.length }} 条数据
                </div>
                <n-data-table
                  v-if="previewData.data.length > 0"
                  :columns="previewData.fields.map(field => ({ title: field, key: field }))"
                  :data="previewData.data"
                  :bordered="false"
                  :max-height="600"
                  class="data-table"
                />
                <div
                  v-else
                  class="empty-table"
                >
                  暂无预览数据
                </div>
              </n-tab-pane>
            </n-tabs>
          </div>

          <div
            v-else
            class="right-side empty-content"
          >
            <div>请选择左侧数据表查看详情</div>
          </div>
        </n-layout-content>
      </n-layout>
    </div>

    <!-- 表注释对话框 -->
    <n-modal
      v-model:show="tableDialog"
      preset="dialog"
      title="编辑表注释"
      @positive-click="saveTable"
    >
      <n-input
        v-model:value="tableComment"
        type="textarea"
        placeholder="请输入表注释"
        :rows="3"
      />
    </n-modal>

    <!-- 字段注释对话框 -->
    <n-modal
      v-model:show="fieldDialog"
      preset="dialog"
      title="编辑字段注释"
      @positive-click="saveField"
    >
      <n-input
        v-model:value="fieldComment"
        type="textarea"
        placeholder="请输入字段注释"
        :rows="3"
      />
    </n-modal>
  </n-message-provider>
</template>

<style lang="scss" scoped>
.table-list-layout {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;

  :deep(.n-layout) {
    height: 100%;
  }

  :deep(.n-layout-sider) {
    height: 100%;
  }

  :deep(.n-layout-content) {
    height: 100%;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
    font-size: 12px;
    color: #666;
    flex-shrink: 0;

    .breadcrumb-item {
      cursor: pointer;
      color: #1890ff;

      &:hover {
        color: #40a9ff;
      }

      &.active {
        color: #666;
        cursor: default;
      }
    }

    .breadcrumb-separator {
      margin: 0 8px;
      color: #999;
    }
  }

  .search-input {
    margin-bottom: 12px;
    flex-shrink: 0;
  }

  .list-content {
    flex: 1;
    overflow-y: auto;
    margin-bottom: 16px;
    min-height: 0;

    .table-list {

      .list-item {
        display: flex;
        align-items: center;
        padding: 10px 12px;
        cursor: pointer;
        border-radius: 4px;
        margin-bottom: 2px;
        font-size: 14px;
        transition: all 0.2s;

        .table-icon {
          margin-right: 8px;
          font-size: 16px;
        }

        .table-name {
          flex: 1;
        }

        &:hover {
          background-color: #f0f0f0;
        }

        &.active {
          background-color: #e6f7ff;
          color: #1890ff;
          font-weight: 500;
        }
      }
    }

    .empty {
      text-align: center;
      color: #999;
      padding: 40px 0;
      font-size: 14px;
    }
  }

  .table-relationship {
    padding-top: 12px;
    border-top: 1px solid #e8e8e8;
    flex-shrink: 0;
  }

  .relationship-content {
    width: 100%;
    height: 100%;
    padding: 12px 12px 12px 0;
    background-color: #f5f6f7;
    overflow: hidden;
    display: flex;
    flex-direction: column;

    :deep(#relationship-container) {
      width: 100%;
      height: 100%;
      background-color: #f5f6f7;
    }
  }

  .right-side {
    flex: 1;
    height: 100%;
    min-width: 0;
    display: flex;
    flex-direction: column;
    background-color: #fff;
    padding: 20px 24px;
    overflow-y: auto;

    .table-header {
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid #e8e8e8;
      flex-shrink: 0;

      .table-title {
        margin-bottom: 8px;

        .table-name-text {
          font-size: 18px;
          font-weight: 600;
          color: #333;
        }
      }

      .table-comment {
        display: flex;
        align-items: center;
        font-size: 14px;
        color: #666;

        .comment-label {
          margin-right: 8px;
        }

        .comment-value {
          flex: 1;
        }

        .edit-btn {
          margin-left: 8px;
          padding: 0;
          min-width: auto;
          height: auto;
          font-size: 14px;
        }
      }
    }

    .content-tabs {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;

      :deep(.n-tabs-nav) {
        margin-bottom: 16px;
        flex-shrink: 0;
      }

      :deep(.n-tabs-pane-wrapper) {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
      }

      :deep(.n-tab-pane) {
        padding: 0;
        height: 100%;
      }
    }

    .preview-info {
      margin-bottom: 12px;
      font-size: 14px;
      color: #666;
    }

    .schema-table-wrapper {
      max-height: 600px;
      overflow-y: auto;
      border: 1px solid #e8e8e8;
      border-radius: 4px;

      :deep(.n-table-wrapper) {
        border: none;
      }
    }

    .data-table {

      :deep(.n-table-wrapper) {
        border: 1px solid #e8e8e8;
        border-radius: 4px;
      }

      :deep(thead th) {
        background-color: #fafafa;
        font-weight: 500;
        color: #333;
        border-bottom: 1px solid #e8e8e8;
        position: sticky;
        top: 0;
        z-index: 1;
      }

      :deep(tbody tr) {

        &:hover {
          background-color: #fafafa;
        }
      }

      :deep(td) {
        border-bottom: 1px solid #f0f0f0;
      }
    }

    .empty-table {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 40px 0;
      color: #999;
      font-size: 14px;
    }

    &.empty-content {
      display: flex;
      align-items: center;
      justify-content: center;
      color: #999;
      font-size: 14px;
      width: 100%;
    }
  }
}

.table-icon-img {
  width: 16px;
  height: 16px;
  object-fit: contain;
}
</style>
