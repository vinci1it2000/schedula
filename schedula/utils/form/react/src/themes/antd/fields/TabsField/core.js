import React from 'react';
import {getUiOptions} from "@rjsf/utils";
import {Tabs, Dropdown, Space, Button, Menu, Typography} from 'antd';
import {
    CopyOutlined,
    CloseOutlined,
    ArrowUpOutlined,
    ArrowDownOutlined,
    ArrowLeftOutlined,
    ArrowRightOutlined,
    EllipsisOutlined,
    LeftOutlined,
    RightOutlined,
    CheckCircleOutlined
} from '@ant-design/icons';
import './TabsField.css'
import cloneDeep from 'lodash/cloneDeep'
import {nanoid} from "nanoid";
import {useLocaleStore} from "../../models/locale";
import ArrayField from "../../../../core/fields/ArrayField";

function keyedToPlainFormData(keyedFormData) {
    if (Array.isArray(keyedFormData)) {
        return keyedFormData.map((keyedItem) => keyedItem.item);
    }
    return [];
}


export function Store({children}) {
    const {getLocale} = useLocaleStore()
    return children({getLocale})
}

export default class TabField extends ArrayField {
    constructor(props) {
        super(props);
        const {uiSchema = {}} = props;
        const {activeKey = 0, collapsed = true} = getUiOptions(uiSchema);
        this.state.activeKey = activeKey
        this.state.collapsed = collapsed
    }

    renderNormalArray() {
        return <Store>
            {({getLocale}) => {
                const locale = getLocale('TabsField')
                const {
                    schema,
                    uiSchema = {},
                    errorSchema,
                    idSchema,
                    name,
                    disabled = false,
                    readonly = false,
                    autofocus = false,
                    registry: registry_,
                    onBlur,
                    onFocus,
                    idPrefix,
                    idSeparator = "_",
                    rawErrors,
                    hideError
                } = this.props;
                const {
                    fields,
                    formContext: formContext_,
                    schemaUtils
                } = registry_;
                const formContext = {...formContext_, parent: this}
                const registry = {...registry_, formContext}
                const {SchemaField} = fields;
                const uiOptions = getUiOptions(uiSchema);
                const {
                    description,
                    removable = true,
                    editable: _editable = true,
                    orderable = true,
                    tabPosition = 'left',
                    itemLabel,
                    fieldReplacesAnyOrOneOf,
                    tabLegend = null,
                    activeKey: activeKey_,
                    collapsed: collapsed_,
                    onlyChildren,
                    ...props
                } = uiOptions;
                const editable = _editable && !(readonly || disabled)
                const _schemaItems = schema.items;
                const {keyedFormData, activeKey: rawActiveKey, collapsed} = this.state;
                const closable = removable && schema.minItems ? keyedFormData.length > schema.minItems : true
                const formData = keyedToPlainFormData(keyedFormData);
                const canAdd = this.canAddItem(formData);
                const collapsedTabMenu = (collapsed && (tabPosition === 'left' || tabPosition === 'right'));
                const activeKey = Math.min(rawActiveKey, keyedFormData.length - 1)
                const tabItems = keyedFormData.map((keyedItem, index) => {
                    if (keyedFormData[index] === undefined)
                        return null
                    const {key, item} = keyedFormData[index];
                    const itemCast = item;
                    const itemSchema = schemaUtils.retrieveSchema(_schemaItems, itemCast);
                    const itemErrorSchema = errorSchema ? (errorSchema[index]) : undefined;
                    const itemIdPrefix = idSchema.$id + idSeparator + index;
                    const itemIdSchema = schemaUtils.toIdSchema(
                        itemSchema,
                        itemIdPrefix,
                        itemCast,
                        idPrefix,
                        idSeparator
                    );

                    let actions = []
                    if (editable && canAdd)
                        actions.push({
                            key: 'clone',
                            label: locale.clone,
                            icon: <CopyOutlined/>
                        })


                    if (editable && orderable) {
                        if (tabPosition === 'left' || tabPosition === 'right') {
                            if (index > 0)
                                actions.push({
                                    key: 'moveup',
                                    label: locale.moveup,
                                    icon: <ArrowUpOutlined/>
                                })
                            if (index < formData.length - 1)
                                actions.push({
                                    key: 'movedown',
                                    label: locale.movedown,
                                    icon: <ArrowDownOutlined/>
                                })
                        } else {
                            if (index > 0)
                                actions.push({
                                    key: 'moveup',
                                    label: locale.moveleft,
                                    icon: <ArrowLeftOutlined/>
                                })
                            if (index < formData.length - 1)
                                actions.push({
                                    key: 'movedown',
                                    label: locale.moveright,
                                    icon: <ArrowRightOutlined/>
                                })
                        }
                    }
                    if (editable && closable)
                        actions.push({
                            key: 'delete',
                            label: locale.delete,
                            icon: <CloseOutlined/>
                        })
                    let label;
                    if (collapsedTabMenu) {
                        if (actions.length) {
                            if (index !== activeKey)
                                actions = [{
                                    key: 'select',
                                    label: locale.select,
                                    icon: <CheckCircleOutlined/>
                                }, ...actions]
                            label = <Dropdown
                                placement="bottomRight"
                                overlay={
                                    <Menu
                                        items={actions}
                                        onClick={({key, domEvent}) => {
                                            if (key === 'delete') {
                                                if (domEvent)
                                                    domEvent.preventDefault()
                                                onDelete(index)
                                            } else if (key === 'clone') {
                                                let newKeyedFormData = [...keyedFormData],
                                                    item = cloneDeep(keyedFormData[index]);
                                                const {onChange} = this.props;
                                                item.key = nanoid()
                                                newKeyedFormData.splice(index + 1, 0, item)
                                                this.setState({
                                                    ...this.state,
                                                    keyedFormData: newKeyedFormData,
                                                    updatedKeyedFormData: true,
                                                    activeKey: index + 1
                                                }, () => {
                                                    onChange(keyedToPlainFormData(newKeyedFormData))
                                                })
                                            } else if (key === 'moveup') {
                                                onReorder(index, index - 1, domEvent)
                                            } else if (key === 'movedown') {
                                                onReorder(index, index + 1, domEvent)
                                            } else if (key === 'select') {
                                                onChangeActive(index)
                                            }
                                        }}
                                    />
                                }
                                onClick={(event) => {
                                    event.preventDefault()
                                    onChangeActive(index)
                                }} arrow>
                                <Button
                                    type={index === activeKey ? "primary" : "text"}>
                                    {index + 1}
                                </Button>
                            </Dropdown>
                        } else {
                            label = [<Button
                                key={`change-${index + 1}`}
                                type={index === activeKey ? "primary" : "text"}
                                onClick={(event) => {
                                    event.preventDefault()
                                    onChangeActive(index)
                                }}>
                                {index + 1}
                            </Button>]
                        }
                        label = <Space.Compact block size={"small"}>
                            {label}
                        </Space.Compact>
                    } else {
                        if (itemLabel) {
                            const itemFormContext = {
                                ...formContext,
                                arrayItemIndex: index
                            }
                            const itemRegistry = {
                                ...registry,
                                formContext: itemFormContext
                            }
                            let fieldItem = <SchemaField
                                key={`${name}-tab-name-${index}`}
                                name={name && `${name}-tab-name-${index}`}
                                index={index}
                                schema={itemSchema}
                                uiSchema={{
                                    ...uiSchema.items,
                                    "ui:layout": {
                                        "path": itemLabel,
                                        "uiSchema": {
                                            "ui:label": "",
                                            "ui:onlyChildren": true,
                                            "ui:disabled": disabled,
                                            "ui:readonly": readonly,
                                            "ui:inputProps": {size: 'small'}
                                        }
                                    },
                                    "ui:onlyChildren": true
                                }}
                                formData={itemCast}
                                formContext={itemFormContext}
                                errorSchema={itemErrorSchema}
                                idPrefix={idPrefix}
                                idSeparator={idSeparator}
                                idSchema={itemIdSchema}
                                required={this.isItemRequired(itemSchema)}
                                onChange={this.onChangeForIndex(index)}
                                onBlur={onBlur}
                                onFocus={(props) => {
                                    onChangeActive(index)
                                    onFocus(props)
                                }}
                                registry={itemRegistry}
                                disabled={disabled}
                                readonly={readonly}
                                hideError={hideError}
                                autofocus={autofocus && index === 0}
                                rawErrors={rawErrors}
                            />
                            label = [
                                <Button
                                    key={`change-${index + 1}`}
                                    type={index === activeKey ? "primary" : "text"}
                                    onClick={(event) => {
                                        event.preventDefault()
                                        onChangeActive(index)
                                    }}>
                                    {index + 1}
                                </Button>,
                                fieldItem
                            ];
                        } else {
                            label = <Button
                                type={index === activeKey ? "primary" : "text"}
                                onClick={(event) => {
                                    event.preventDefault()
                                    onChangeActive(index)
                                }}>
                                {(name && `${name}-${index}`) || `item-${index}`}
                            </Button>
                        }
                        label = <Space.Compact block size={"small"}>
                            {label}
                            {actions.length ? <Dropdown
                                placement="bottomRight"
                                overlay={
                                    <Menu
                                        items={actions}
                                        onClick={({key, domEvent}) => {
                                            if (key === 'delete') {
                                                if (domEvent)
                                                    domEvent.preventDefault()
                                                onDelete(index)
                                            } else if (key === 'clone') {
                                                let newKeyedFormData = [...keyedFormData],
                                                    item = cloneDeep(keyedFormData[index]);
                                                const {onChange} = this.props;
                                                item.key = nanoid()
                                                newKeyedFormData.splice(index + 1, 0, item)
                                                this.setState({
                                                    ...this.state,
                                                    keyedFormData: newKeyedFormData,
                                                    updatedKeyedFormData: true,
                                                    activeKey: index + 1
                                                }, () => {
                                                    onChange(keyedToPlainFormData(newKeyedFormData))
                                                })
                                            } else if (key === 'moveup') {
                                                onReorder(index, index - 1, domEvent)
                                            } else if (key === 'movedown') {
                                                onReorder(index, index + 1, domEvent)
                                            }
                                        }}
                                    />
                                }
                                onClick={(event) => {
                                    event.preventDefault()
                                    onChangeActive(index)
                                }} arrow>
                                <Button
                                    type={index === activeKey ? "primary" : "text"}
                                    icon={<EllipsisOutlined/>}/>
                            </Dropdown> : null}
                        </Space.Compact>
                    }

                    const itemFormContext = {
                        ...formContext,
                        arrayItemIndex: index
                    }
                    const itemRegistry = {
                        ...registry,
                        formContext: itemFormContext
                    }
                    return {
                        key: index,
                        closable,
                        label,
                        children: <div className={'hide-fieldset-border h-100'}>
                            {<SchemaField
                                key={key}
                                name={name}
                                index={index}
                                schema={itemSchema}
                                uiSchema={{"ui:onlyChildren": true, ...uiSchema.items}}
                                formData={itemCast}
                                formContext={itemFormContext}
                                errorSchema={itemErrorSchema}
                                idPrefix={idPrefix}
                                idSeparator={idSeparator}
                                idSchema={itemIdSchema}
                                required={this.isItemRequired(itemSchema)}
                                onChange={this.onChangeForIndex(index)}
                                onBlur={onBlur}
                                onFocus={onFocus}
                                registry={itemRegistry}
                                disabled={disabled}
                                readonly={readonly}
                                hideError={hideError}
                                autofocus={autofocus && index === 0}
                                rawErrors={rawErrors}
                            />}
                        </div>
                    }
                });

                const onChangeActive = (activeKey) => {
                    this.setState({...this.state, activeKey})
                };
                const onDelete = (targetKey) => {
                    this.onDropIndexClick(targetKey)()
                    if (keyedFormData.length > 1 && targetKey <= activeKey) {
                        this.setState({
                            ...this.state,
                            activeKey: Math.max(activeKey - 1, 0)
                        })
                    }
                };
                const onReorder = (index, newIndex, event) => {
                    this.onReorderClick(index, newIndex)(event)
                    if (index === activeKey) {
                        this.setState({
                            ...this.state,
                            activeKey: newIndex
                        })
                    } else if (newIndex === activeKey) {
                        this.setState({
                            ...this.state,
                            activeKey: index
                        })
                    }
                };
                const onEdit = (targetKey, action) => {
                    if (action === 'add') {
                        this.onAddClick(targetKey);
                        this.setState({
                            ...this.state,
                            activeKey: keyedFormData.length
                        })
                    } else {
                        onDelete(targetKey)
                    }
                };
                const collapseButton = <Button
                    type="primary" shape="circle"
                    icon={(tabPosition === 'left' ? collapsed : !collapsed) ?
                        <RightOutlined/> :
                        <LeftOutlined/>}
                    onClick={() => {
                        this.setState({
                            ...this.state,
                            collapsed: !collapsed
                        })
                    }}/>
                return <Tabs
                    key={idSchema.$id}
                    style={{height: '100%'}}
                    hideAdd={!(editable && canAdd)}
                    tabBarExtraContent={{
                        "left": <Space.Compact
                            block size="small"
                            style={{
                                justifyContent: collapsedTabMenu ? 'center' : (tabPosition === 'left' ? 'right' : (tabPosition === 'right' ? 'left' : 'center'))
                            }}>
                            {tabPosition === 'right' ? collapseButton : null}
                            {collapsedTabMenu || !tabLegend ? null :
                                <Typography.Text
                                    style={{
                                        width: '100%',
                                        textAlign: 'center'
                                    }}>{tabLegend}</Typography.Text>}
                            {tabPosition === 'left' ? collapseButton : null}
                        </Space.Compact>
                    }}
                    tabPosition={tabPosition}
                    type="editable-card"
                    activeKey={Math.min(activeKey, tabItems.length - 1)}
                    onEdit={onEdit}
                    items={tabItems}
                    {...props}
                />
            }}
        </Store>
    }
}
