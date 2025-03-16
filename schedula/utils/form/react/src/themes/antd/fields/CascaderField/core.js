import {Cascader} from 'antd';
import React, {useMemo, useCallback} from "react";
import {getUiOptions} from "@rjsf/utils";
import {useLocaleStore} from "../../models/locale";
import get from 'lodash/get'
import has from 'lodash/has'
import './CascaderField.css'

function buildOptions(schema, names) {
    const name = names[0], nextNames = names.slice(1),
        {oneOf = [], properties = {}} = schema;
    let options;
    if (has(properties, `${name}.enum`)) {
        options = get(properties, `${name}.enum`).map(k => ({
            title: k,
            const: k
        }));
    } else {
        options = get(properties, `${name}.oneOf`, []);
    }
    return options.map(({title: label, const: value}) => {
        if (nextNames.length) {
            const subSchema = oneOf.find(({properties = {}}) => (
                get(properties, `${name}.const`, null) === value
            )), children = buildOptions(subSchema, nextNames);
            if (subSchema && children.length)
                return {label, value, children}
        }
        return {label, value}
    })

}

export default function CascaderField(
    {
        schema:{
            description, // rendered by the parent.
            ...schema
        },
        uiSchema,
        formData = {},
        onChange,
        registry,
        rawErrors,
        errorSchema,
        ...props
    }
) {
    const {getLocale} = useLocaleStore()
    const locale = getLocale('global')
    const uiOptions = getUiOptions(uiSchema),
        {
            cascaderProps: {
                names,
                placement = "bottomLeft",
                showSearch,
                ...cascaderProps
            }
        } = uiOptions,
        valueOptions = useMemo(
            () => buildOptions(schema, names), [schema, names]
        );
    let value = []
    names.reduce((valid, name) => {
        if (!(valid && formData.hasOwnProperty(name)))
            return false
        value.push(formData[name])
        return true
    }, true)
    const handleOnChange = useCallback((values) => {
        let newFormData = {...formData}
        names.forEach((name, index) => {
            let value = (values || [])[index]
            if (value === undefined) {
                delete newFormData[name]
            } else {
                newFormData[name] = value
            }
        })
        onChange(newFormData)
    }, [formData, names, onChange]);

    const filter = (inputValue, path) => path.some(
        (option) => String(option.label).toLowerCase().indexOf(String(inputValue).toLowerCase()) > -1
    );
    const {fields: {BaseField}} = registry
    return <BaseField
        schema={schema}
        errorSchema={{__errors: rawErrors, ...errorSchema}}
        uiSchema={{
            displayLabel: true,
            "ui:classNames": ['unset-height child-item-margin-0'],
            ...uiSchema
        }}
        formData={formData}
        registry={registry}
        {...props}>
        <Cascader
            className="schedula-cascader"
            popupClassName="schedula-cascader"
            status={rawErrors && rawErrors.length > 0 ? "error" : null}
            style={{width: '100%'}}
            value={value}
            options={valueOptions}
            onChange={handleOnChange}
            placement={placement}
            dropdownMatchSelectWidth={true}
            placeholder={locale.placeholder}
            showSearch={{
                filter,
                matchInputWidth: true,
                limit: 20, ...showSearch
            }}
            {...cascaderProps}
        />
    </BaseField>
}