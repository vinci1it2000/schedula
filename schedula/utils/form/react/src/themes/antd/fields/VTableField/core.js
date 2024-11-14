import React from 'react';
import {Table, Col, Row} from 'antd';
import {getUiOptions, getTemplate} from "@rjsf/utils";
import {ConfigConsumer} from "antd/lib/config-provider/context";
import classNames from "classnames";
import './TableField.css'
import {
    DownOutlined,
    RightOutlined
} from '@ant-design/icons';
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


export default class VTableField extends ArrayField {
    render() {
        return <Store>{({getLocale}) => {
            const {
                schema,
                uiSchema = {},
                errorSchema,
                idSchema,
                name,
                disabled = false,
                readonly = false,
                autofocus = false,
                required = false,
                registry: registry_,
                onBlur,
                onFocus,
                idPrefix,
                idSeparator = "_",
                rawErrors,
                hideError
            } = this.props;
            const {fields, formContext: formContext_, schemaUtils} = registry_;
            const formContext = {...formContext_, parent: this}
            const registry = {...registry_, formContext}
            const {SchemaField} = fields
            const uiOptions = getUiOptions(uiSchema);
            const {
                rows: rawRows,
                columnIndex = {},
                removeEmpty = false,
                title = schema.title === undefined ? name : schema.title,
                ...props
            } = uiOptions;
            const _schemaItems = schema.items;
            const formData = keyedToPlainFormData(this.state.keyedFormData);
            const field = this
            const availableKeys = new Set(formData.reduce((a, v) => [...a, ...Object.keys(v)], []))
            const filterRows = (rows) => (
                rows.filter(v => !removeEmpty || v.render || availableKeys.has(v.dataIndex)).map(v => {
                    return {...v, children: filterRows(v.children || [])}
                })
            )
            const rows = filterRows(rawRows)

            function defineTableProps(rows) {
                let tableColumns = [{
                    rowScope: 'row',
                    ...columnIndex,
                    key: 'id',
                    dataIndex: 'id',
                }, ...formData.map((d, i) => {
                        const renderCell = (cell) => {
                            const {keyedFormData} = field.state
                            if (keyedFormData[i] === undefined)
                                return null
                            const {item} = keyedFormData[i];
                            const itemCast = item;
                            const itemSchema = schemaUtils.retrieveSchema(_schemaItems, itemCast);
                            const itemErrorSchema = errorSchema ? (errorSchema[i]) : undefined;
                            const itemIdPrefix = idSchema.$id + idSeparator + i;
                            const itemIdSchema = schemaUtils.toIdSchema(
                                itemSchema,
                                itemIdPrefix,
                                itemCast,
                                idPrefix,
                                idSeparator
                            );
                            const itemFormContext = {
                                ...formContext,
                                arrayItemIndex: i
                            }
                            const itemRegistry = {
                                ...registry,
                                formContext: itemFormContext
                            }
                            return <SchemaField
                                key={`${name}-${i}`}
                                name={name && `${name}-${cell.dataIndex}-${i}`}
                                index={i}
                                schema={itemSchema}
                                uiSchema={{
                                    ...uiSchema.items,
                                    "ui:layout": {
                                        ...(cell.hasOwnProperty('dataIndex') ? {
                                            "path": cell.dataIndex,
                                            "uiSchema": {
                                                "ui:label": '',
                                                "ui:onlyChildren": true,
                                                "ui:disabled": disabled,
                                                "ui:readonly": readonly,
                                                ...cell.uiSchema
                                            }
                                        } : cell)
                                    },
                                    "ui:onlyChildren": true
                                }}
                                formData={itemCast}
                                formContext={itemFormContext}
                                errorSchema={itemErrorSchema}
                                idPrefix={idPrefix}
                                idSeparator={idSeparator}
                                idSchema={itemIdSchema}
                                required={field.isItemRequired(itemSchema)}
                                onChange={field.onChangeForIndex(i)}
                                onBlur={onBlur}
                                onFocus={onFocus}
                                registry={itemRegistry}
                                disabled={disabled}
                                readonly={readonly}
                                hideError={hideError}
                                autofocus={autofocus && i === 0}
                                rawErrors={rawErrors}
                            />
                        };
                        return {
                            key: i,
                            dataIndex: i,
                            title: renderCell(columnIndex),
                            render: (text, record, index) => (renderCell(rows[index]))
                        }
                    }
                )]
                let dataSource = rows.map((item, index) => {
                    return formData.reduce((a, v, i) => {
                        a[i] = v[item.dataIndex];
                        return a
                    }, {id: item.title, key: index});
                })

                const expandable = {
                    expandedRowRender: (record) => (
                        <Table
                            size={props.size || "small"}
                            {...defineTableProps(rows[record.key].children)}/>
                    ),
                    rowExpandable: (record) => (rows[record.key].children || []).length > 0,
                    expandIcon: ({expanded, onExpand, record}) => (
                        (rows[record.key].children || []).length > 0 ?
                            expanded ? <DownOutlined
                                    onClick={e => onExpand(record, e)}/> :
                                <RightOutlined
                                    onClick={e => onExpand(record, e)}/>
                            : null
                    )
                }

                return {
                    showHeader: false,
                    className: 'vertical-table',
                    columns: dataSource.length ? tableColumns : [],
                    dataSource,
                    pagination: false,
                    expandable
                }
            }

            const {labelAlign = "right", rowGutter = 24} = formContext;
            const ArrayFieldTitleTemplate = getTemplate("ArrayFieldTitleTemplate", registry, uiOptions);

            return <ConfigConsumer key={idSchema.$id}>
                {(configProps) => {
                    const {getPrefixCls} = configProps;
                    const prefixCls = getPrefixCls("form");
                    const labelClsBasic = `${prefixCls}-item-label`;
                    const labelColClassName = classNames(
                        labelClsBasic,
                        labelAlign === "left" && `${labelClsBasic}-left`,
                        'ant-table-label-custom'
                        //labelCol.className,
                    );
                    return (
                        <Table
                            locale={getLocale('Table')}
                            caption={
                                <Row justify="space-between"
                                     align="middle">
                                    <Col>
                                        <Row gutter={rowGutter}>
                                            {title && (
                                                <Col
                                                    className={labelColClassName}
                                                    span={24}>
                                                    <ArrayFieldTitleTemplate
                                                        idSchema={idSchema}
                                                        required={required}
                                                        title={title}
                                                        schema={schema}
                                                        uiSchema={uiSchema}
                                                        registry={registry}
                                                    />
                                                </Col>
                                            )}
                                        </Row>
                                    </Col>
                                </Row>}
                            key={idSchema.$id}
                            size="small"
                            {...defineTableProps(rows)}
                            showHeader={true}
                            {...props}/>
                    );
                }}
            </ConfigConsumer>
        }}</Store>
    }
}
