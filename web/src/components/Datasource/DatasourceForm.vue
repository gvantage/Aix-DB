<script lang="ts" setup>
import type { FormInst, FormRules } from 'naive-ui'
import { computed, reactive, ref, watch } from 'vue'

interface Props {
  show: boolean
  datasource?: any
}

const props = withDefaults(defineProps<Props>(), {
  show: false,
  datasource: null,
})

const emit = defineEmits(['update:show', 'success'])

// 数据源类型选项
const datasourceTypes = [
  { label: 'MySQL', value: 'mysql' },
  { label: 'PostgreSQL', value: 'pg' },
  { label: 'Oracle', value: 'oracle' },
  { label: 'SQL Server', value: 'sqlServer' },
  { label: 'ClickHouse', value: 'ck' },
]

// 需要 Schema 的数据源类型
const needSchemaTypes = ['sqlServer', 'pg', 'oracle']

// 表单引用
const formRef = ref<FormInst | null>(null)

// 表单数据
const formData = reactive({
  name: '',
  description: '',
  type: 'mysql',
  host: '',
  port: 3306,
  username: '',
  password: '',
  database: '',
  dbSchema: '',
  extraJdbc: '',
  timeout: 30,
  mode: 'service_name', // Oracle 连接模式
})

// 表单验证规则
const rules: FormRules = {
  name: [
    { required: true, message: '请输入数据源名称', trigger: 'blur' },
    {
      validator: (rule: any, value: string) => {
        if (!value) {
          return true // required 规则会处理空值
        }
        if (value.length < 1 || value.length > 50) {
          return new Error('名称长度在1-50个字符')
        }
        return true
      },
      trigger: 'blur',
    },
  ],
  type: [
    { required: true, message: '请选择数据源类型', trigger: 'change' },
  ],
  host: [
    { required: true, message: '请输入主机地址', trigger: 'blur' },
  ],
  port: [
    {
      validator: (rule: any, value: any) => {
        if (value === null || value === undefined || value === '' || value === 0) {
          return new Error('请输入端口号')
        }
        const num = Number(value)
        if (Number.isNaN(num)) {
          return new Error('请输入有效的端口号')
        }
        if (num < 1 || num > 65535) {
          return new Error('端口号范围1-65535')
        }
        return true
      },
      trigger: ['blur', 'input'],
    },
  ],
  database: [
    { required: true, message: '请输入数据库名', trigger: 'blur' },
  ],
  dbSchema: [
    { required: true, message: '请输入Schema', trigger: 'blur' },
  ],
}

// 状态
const loading = ref(false)
const testing = ref(false)
const currentStep = ref(1) // 1: 基本信息, 2: 选择表
const tableList = ref<any[]>([])
const selectedTables = ref<string[]>([])
const tableListLoading = ref(false)

// 是否显示 Schema 字段
const showSchema = computed(() => needSchemaTypes.includes(formData.type))

// 是否显示 Oracle 连接模式
const showOracleMode = computed(() => formData.type === 'oracle')

// 监听数据源类型变化，设置默认端口
watch(() => formData.type, (newType) => {
  const defaultPorts: Record<string, number> = {
    mysql: 3306,
    pg: 5432,
    oracle: 1521,
    sqlServer: 1433,
    ck: 8123,
  }
  if (defaultPorts[newType]) {
    formData.port = defaultPorts[newType]
  }
})

// 初始化表单
const initForm = () => {
  if (props.datasource) {
    // 编辑模式
    formData.name = props.datasource.name || ''
    formData.description = props.datasource.description || ''
    formData.type = props.datasource.type || 'mysql'
    // TODO: 解密配置信息
    // const config = JSON.parse(decrypt(props.datasource.configuration))
    // Object.assign(formData, config)
  } else {
    // 新建模式
    Object.assign(formData, {
      name: '',
      description: '',
      type: 'mysql',
      host: '',
      port: 3306,
      username: '',
      password: '',
      database: '',
      dbSchema: '',
      extraJdbc: '',
      timeout: 30,
      mode: 'service_name',
    })
  }
  currentStep.value = 1
  selectedTables.value = []
  tableList.value = []
}

// 测试连接
const testConnection = async () => {
  if (!formRef.value) {
    return
  }
  await formRef.value.validate((errors) => {
    if (errors) {}
  })

  testing.value = true
  try {
    const config = buildConfiguration()
    const url = new URL(`${location.origin}/sanic/datasource/check`)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id: props.datasource?.id,
        type: formData.type,
        configuration: JSON.stringify(config),
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200 && result.data?.connected) {
      window.$ModalMessage.success('连接成功')
      // 连接成功后获取表列表
      await fetchTableList()
    } else {
      window.$ModalMessage.error(result.data?.error_message || '连接失败')
    }
  } catch (error) {
    console.error('测试连接失败:', error)
    window.$ModalMessage.error('测试连接失败')
  } finally {
    testing.value = false
  }
}

// 获取表列表
const fetchTableList = async () => {
  tableListLoading.value = true
  try {
    const config = buildConfiguration()
    const url = new URL(`${location.origin}/sanic/datasource/getTablesByConf`)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: formData.type,
        configuration: JSON.stringify(config),
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      tableList.value = result.data || []
      // 如果是编辑模式，加载已选中的表
      if (props.datasource?.id) {
        const tablesUrl = new URL(`${location.origin}/sanic/datasource/tableList/${props.datasource.id}`)
        const tablesResponse = await fetch(tablesUrl, {
          method: 'POST',
        })

        if (!tablesResponse.ok) {
          throw new Error(`HTTP error! status: ${tablesResponse.status}`)
        }

        const tablesResult = await tablesResponse.json()
        if (tablesResult.code === 200) {
          selectedTables.value = tablesResult.data
            .filter((t: any) => t.checked)
            .map((t: any) => t.table_name)
        }
      }
    } else {
      window.$ModalMessage.error(result.msg || '获取表列表失败')
    }
  } catch (error) {
    console.error('获取表列表失败:', error)
    window.$ModalMessage.error('获取表列表失败')
  } finally {
    tableListLoading.value = false
  }
}

// 构建配置对象
const buildConfiguration = () => {
  return {
    host: formData.host,
    port: formData.port,
    username: formData.username,
    password: formData.password,
    database: formData.database,
    dbSchema: formData.dbSchema || formData.database,
    extraJdbc: formData.extraJdbc,
    timeout: formData.timeout,
    mode: formData.mode,
  }
}

// 下一步（选择表）
const handleNext = async () => {
  if (!formRef.value) {
    return
  }
  await formRef.value.validate(async (errors) => {
    if (errors) {
      return
    }
    // 先测试连接
    await testConnection()
    if (tableList.value.length > 0) {
      currentStep.value = 2
    }
  })
}

// 上一步
const handlePrev = () => {
  currentStep.value = 1
}

// 全选/取消全选
const handleSelectAll = () => {
  if (selectedTables.value.length === tableList.value.length) {
    selectedTables.value = []
  } else {
    selectedTables.value = tableList.value.map((table) => table.tableName)
  }
}

// 是否全选
const isAllSelected = computed(() => {
  return tableList.value.length > 0 && selectedTables.value.length === tableList.value.length
})

// 保存数据源
const handleSave = async () => {
  if (selectedTables.value.length === 0) {
    window.$ModalMessage.warning('请至少选择一个表')
    return
  }

  loading.value = true
  try {
    const config = buildConfiguration()
    // TODO: 加密配置
    const configuration = JSON.stringify(config)

    const tables = selectedTables.value.map((tableName) => {
      const table = tableList.value.find((t) => t.tableName === tableName)
      return {
        table_name: tableName,
        table_comment: table?.tableComment || '',
      }
    })

    const requestData = {
      name: formData.name,
      description: formData.description,
      type: formData.type,
      type_name: datasourceTypes.find((t) => t.value === formData.type)?.label || formData.type,
      configuration,
      tables,
    }

    let response
    let dsId = props.datasource?.id
    if (props.datasource?.id) {
      // 更新
      const url = new URL(`${location.origin}/sanic/datasource/update`)
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: props.datasource.id,
          ...requestData,
        }),
      })
    } else {
      // 新建
      const url = new URL(`${location.origin}/sanic/datasource/add`)
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      })
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    if (result.code === 200) {
      // 优先使用返回的 id（新建场景）
      dsId = result.data?.id || dsId
      // 将选中表同步到后端表/字段（调用新接口，清理未选表）
      if (dsId) {
        try {
          const syncUrl = new URL(`${location.origin}/sanic/datasource/syncTables/${dsId}`)
          await fetch(syncUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(tables),
          })
        } catch (syncErr) {
          console.error('同步表列表失败:', syncErr)
        }
      }

      window.$ModalMessage.success(props.datasource?.id ? '更新成功' : '创建成功')
      emit('success')
      handleClose()
    } else {
      window.$ModalMessage.error(result.msg || '保存失败')
    }
  } catch (error) {
    console.error('保存数据源失败:', error)
    window.$ModalMessage.error('保存数据源失败')
  } finally {
    loading.value = false
  }
}

// 关闭对话框
const handleClose = () => {
  emit('update:show', false)
  initForm()
}

// 监听 show 变化
watch(() => props.show, (newVal) => {
  if (newVal) {
    initForm()
  }
})
</script>

<template>
  <n-modal
    :show="show"
    :mask-closable="false"
    preset="card"
    :title="datasource ? '编辑数据源' : '新建数据源'"
    class="datasource-modal"
    transform-origin="center"
    :style="{ width: '800px' }"
    :content-style="{ maxHeight: '70vh', overflow: 'auto' }"
    @update:show="(val) => emit('update:show', val)"
    @close="handleClose"
  >
    <n-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-placement="left"
      label-width="100px"
      require-mark-placement="right-hanging"
    >
      <!-- 第一步：基本信息 -->
      <div v-if="currentStep === 1">
        <n-form-item
          label="数据源名称"
          path="name"
        >
          <n-input
            v-model:value="formData.name"
            placeholder="请输入数据源名称"
            clearable
          />
        </n-form-item>

        <n-form-item label="描述">
          <n-input
            v-model:value="formData.description"
            type="textarea"
            placeholder="请输入描述（可选）"
            :rows="2"
            clearable
          />
        </n-form-item>

        <n-form-item
          label="数据源类型"
          path="type"
        >
          <n-select
            v-model:value="formData.type"
            :options="datasourceTypes"
            placeholder="请选择数据源类型"
          />
        </n-form-item>

        <n-form-item
          label="主机地址"
          path="host"
        >
          <n-input
            v-model:value="formData.host"
            placeholder="请输入主机地址"
            clearable
          />
        </n-form-item>

        <n-form-item
          label="端口"
          path="port"
        >
          <n-input-number
            v-model:value="formData.port"
            :min="1"
            :max="65535"
            placeholder="请输入端口号"
            :show-button="false"
            style="width: 100%"
          />
        </n-form-item>

        <n-form-item label="用户名">
          <n-input
            v-model:value="formData.username"
            placeholder="请输入用户名"
            clearable
          />
        </n-form-item>

        <n-form-item label="密码">
          <n-input
            v-model:value="formData.password"
            type="password"
            placeholder="请输入密码"
            show-password-on="click"
            clearable
          />
        </n-form-item>

        <n-form-item
          label="数据库名"
          path="database"
        >
          <n-input
            v-model:value="formData.database"
            placeholder="请输入数据库名"
            clearable
          />
        </n-form-item>

        <n-form-item
          v-if="showSchema"
          label="Schema"
          path="dbSchema"
        >
          <n-input
            v-model:value="formData.dbSchema"
            placeholder="请输入Schema"
            clearable
          />
        </n-form-item>

        <n-form-item
          v-if="showOracleMode"
          label="连接模式"
          path="mode"
        >
          <n-radio-group v-model:value="formData.mode">
            <n-radio value="service_name">
              Service Name
            </n-radio>
            <n-radio value="sid">
              SID
            </n-radio>
          </n-radio-group>
        </n-form-item>

        <n-form-item label="额外参数">
          <n-input
            v-model:value="formData.extraJdbc"
            placeholder="例如: useSSL=false&serverTimezone=UTC"
            clearable
          />
        </n-form-item>

        <n-form-item label="超时时间（秒）">
          <n-input-number
            v-model:value="formData.timeout"
            :min="1"
            :max="300"
            placeholder="默认30秒"
            style="width: 100%"
          />
        </n-form-item>
      </div>

      <!-- 第二步：选择表 -->
      <div v-if="currentStep === 2">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
          <n-text>已选择 {{ selectedTables.length }} / {{ tableList.length }} 个表</n-text>
          <n-button
            size="small"
            @click="handleSelectAll"
          >
            {{ isAllSelected ? '取消全选' : '全选' }}
          </n-button>
        </div>

        <n-spin :show="tableListLoading">
          <div style="max-height: 400px; overflow-y: auto">
            <n-checkbox-group v-model:value="selectedTables">
              <n-space
                vertical
                :size="8"
              >
                <n-checkbox
                  v-for="table in tableList"
                  :key="table.tableName"
                  :value="table.tableName"
                  :label="table.tableName"
                >
                  <template #label>
                    <div style="display: flex; align-items: center; gap: 8px">
                      <span>{{ table.tableName }}</span>
                      <n-text
                        v-if="table.tableComment"
                        depth="3"
                        style="font-size: 12px"
                      >
                        {{ table.tableComment }}
                      </n-text>
                    </div>
                  </template>
                </n-checkbox>
              </n-space>
            </n-checkbox-group>
          </div>
        </n-spin>
      </div>
    </n-form>
    <template #action>
      <div class="modal-actions">
        <n-button @click="handleClose">
          取消
        </n-button>

        <n-button
          v-if="currentStep === 2"
          @click="handlePrev"
        >
          上一步
        </n-button>

        <n-button
          v-if="currentStep === 1"
          :loading="testing"
          @click="testConnection"
        >
          测试连接
        </n-button>

        <n-button
          v-if="currentStep === 1"
          type="primary"
          @click="handleNext"
        >
          下一步
        </n-button>

        <n-button
          v-if="currentStep === 2"
          type="primary"
          :loading="loading"
          @click="handleSave"
        >
          保存
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style lang="scss" scoped>
:deep(.n-form-item) {
  margin-bottom: 0;
}

// 确保输入框有背景色，防止透明

:deep(.n-input) {
  background-color: var(--n-color) !important;
}

:deep(.n-input-wrapper) {
  background-color: var(--n-color) !important;
}

:deep(.n-input__input-el) {
  background-color: transparent;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  width: 100%;
  margin-top: 0;
  border-top: 1px solid var(--n-divider-color);
  background-color: var(--n-card-color, #fff);
}
</style>
