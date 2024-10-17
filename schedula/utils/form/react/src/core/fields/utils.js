import React, {Suspense, useMemo, useContext} from "react";
import {
    ADDITIONAL_PROPERTY_FLAG,
    PROPERTIES_KEY
} from "@rjsf/utils";
import get from "lodash/get";
import has from "lodash/has";
import isObject from "lodash/isObject";
import cloneDeepWith from "lodash/cloneDeepWith";
import set from "lodash/set";
import assign from "lodash/assign";


export function getComponents({render, component}) {
    return get(
        render, `formContext.components.${component}`, components[component]
    )
}

export function getComponentDomains({render, component}) {
    return get(
        render, `formContext.domains.${component}`, domains[component]
    )
}

const customizerCloneDeep = (val) => {
    return val && (val.constructor === Object || val.constructor === Array) ? undefined : val
}

export function createLayoutElement({key, layout, render, isArray}) {
    const {path, configProvider, ..._layout} = layout;
    let element;
    if (path) {
        element = <LayoutComponent
            key={key} id={key} layout={{path, ..._layout}} render={render}
            isArray={isArray}
        />
    } else {
        element = <LayoutElement
            key={key} id={key} layout={_layout} render={render}
        />
    }
    if (configProvider) {
        const {
            registry: {templates: {ConfigProvider}},
            formContext: {form}
        } = render
        element = <ConfigProvider form={form} {...configProvider}>
            {element}
        </ConfigProvider>
    }
    return element;
}

export function LayoutComponent({id: key, layout, render, isArray}) {
    const {
        path,
        component,
        eothers = {},
        fothers = {},
        vothers = {},
        children,
        ...others_
    } = layout;
    const {formContext: {FormContext}} = render
    const {form} = useContext(FormContext)
    const others = useMemo(() => {
        let others = cloneDeepWith(others_, customizerCloneDeep);
        Object.entries(eothers).forEach(([path, layout], index) => {
            set(others, path, createLayoutElement({
                key: `${key}-ele-${index}`,
                layout,
                render
            }))
        });
        Object.entries(fothers).forEach(([path, func]) => {
            set(others, path, form.compileFunc(func).bind(null, render, layout))
        });
        Object.entries(vothers).forEach(([path, func]) => {
            set(others, path, form.compileFunc(func)(render, layout))
        });
        if (others.uiSchema) {
            others.uiSchema = fixLayoutOption(others.uiSchema)
        }
        return others;
    }, [eothers, fothers, vothers, form, form.state, form.state.formData, others_, render, layout, key])

    let fieldPath = path.split('/'), name = fieldPath[0];
    fieldPath = fieldPath.slice(1).join('/')
    let contentProps
    const {SchemaField} = render
    if (name === '..') {
        const {
            schema,
            uiSchema = {},
            formData,
            errorSchema,
            idSchema,
            name,
            disabled = false,
            readonly = false,
            hideError,
            idPrefix,
            idSeparator,
            formContext,
            registry,
        } = render.parent.props;
        const {parent} = formContext

        contentProps = {
            key: `${key}-${name}`,
            idPrefix,
            idSeparator,
            formContext,
            schema,
            uiSchema: cloneDeepWith(uiSchema, customizerCloneDeep),
            errorSchema,
            idSchema,
            formData,
            registry,
            disabled,
            readonly,
            onChange: parent.props.onChange,
            onBlur: parent.props.onBlur,
            onFocus: parent.props.onFocus,
            hideError,
        }
    } else if (name === '.') {
        const {
            readonly,
            disabled,
            idSchema,
            uiSchema,
            schema,
            formData,
            formContext,
            registry,
            errorSchema,
            idPrefix,
            idSeparator,
            hideError,
            parent
        } = render

        contentProps = {
            key: `${key}-${name}`,
            idPrefix,
            idSeparator,
            formContext,
            schema,
            uiSchema: cloneDeepWith(uiSchema, customizerCloneDeep),
            errorSchema,
            idSchema,
            formData,
            registry,
            disabled,
            readonly,
            onChange: parent.props.onChange,
            onBlur: parent.props.onBlur,
            onFocus: parent.props.onFocus,
            hideError,
        }
    } else if (name === '#') {
        const {
            readonly,
            disabled,
            idPrefix,
            idSeparator = '_',
            formContext,
            idSchema
        } = render
        const {
            schema,
            uiSchema,
            formData,
            errorSchema
        } = form.state;

        const registry = form.getRegistry();
        const {schemaUtils} = registry
        const itemIdPrefix = idSchema.$id + idSeparator + name;
        const itemSchema = schemaUtils.retrieveSchema(schema, formData);
        const itemIdSchema = schemaUtils.toIdSchema(
            itemSchema,
            itemIdPrefix,
            formData,
            idPrefix,
            idSeparator
        );
        contentProps = {
            key: `${key}-${name}`,
            idPrefix,
            idSeparator,
            formContext,
            schema: cloneDeepWith(schema, customizerCloneDeep),
            uiSchema: cloneDeepWith(uiSchema, customizerCloneDeep),
            errorSchema,
            idSchema: itemIdSchema,
            formData,
            registry,
            disabled,
            readonly,
            onChange: form.onChange,
            onBlur: form.onBlur,
            onFocus: form.onFocus,
        }
    } else if (isArray) {
        const {
            readonly,
            disabled,
            idSchema,
            uiSchema,
            schema,
            name: arrayName,
            formContext,
            registry,
            errorSchema,
            idPrefix,
            idSeparator = '_',
            hideError,
            parent,
            onBlur,
            onFocus,
            autofocus,
            rawErrors
        } = render
        const index = Number(name)
        const {keyedFormData} = parent.state
        if (keyedFormData[index] === undefined)
            return null
        const {schemaUtils} = registry
        const {key, item} = keyedFormData[index];
        const itemCast = item;
        const itemSchema = schemaUtils.retrieveSchema(schema.items, itemCast);
        const itemErrorSchema = errorSchema ? (errorSchema[index]) : undefined;
        const itemIdPrefix = idSchema.$id + idSeparator + index;
        const itemIdSchema = schemaUtils.toIdSchema(
            itemSchema,
            itemIdPrefix,
            itemCast,
            idPrefix,
            idSeparator
        );
        const itemFormContext = {...formContext, arrayItemIndex: index}
        const itemRegistry = {...registry, formContext: itemFormContext}

        contentProps = {
            key: `${key}-${index}`,
            name: name && `${arrayName}-${index}`,
            index,
            required: parent.isItemRequired(itemSchema),
            schema: itemSchema,
            uiSchema: cloneDeepWith(uiSchema.items || {}, customizerCloneDeep),
            errorSchema: itemErrorSchema,
            idSchema: itemIdSchema,
            idPrefix,
            idSeparator,
            formData: itemCast,
            formContext: itemFormContext,
            onChange: parent.onChangeForIndex(index),
            onBlur,
            onFocus,
            registry: itemRegistry,
            disabled,
            readonly,
            hideError,
            rawErrors,
            autofocus: autofocus && index === 0
        }
    } else {
        const {
            readonly,
            disabled,
            idSchema,
            uiSchema,
            schema,
            formData,
            formContext,
            registry,
            errorSchema,
            idPrefix,
            idSeparator,
            onBlur,
            onFocus,
            hideError,
            parent
        } = render
        const addedByAdditionalProperties = has(schema, [
            PROPERTIES_KEY,
            name,
            ADDITIONAL_PROPERTY_FLAG,
        ]);
        let fieldUiSchema = fixLayoutOption(addedByAdditionalProperties
            ? uiSchema.additionalProperties
            : uiSchema[name]);

        const fieldIdSchema = get(idSchema, [name], {});
        contentProps = {
            key: `${key}-${name}`,
            name,
            required: parent.isRequired(name),
            schema: get(schema, [PROPERTIES_KEY, name], {}),
            uiSchema: cloneDeepWith(fieldUiSchema || {}, customizerCloneDeep),
            errorSchema: get(errorSchema, name),
            idSchema: fieldIdSchema,
            idPrefix,
            idSeparator,
            formData: get(formData, name),
            formContext,
            wasPropertyKeyModified: parent.state.wasPropertyKeyModified,
            onKeyChange: parent.onKeyChange(name),
            onChange: parent.onPropertyChange(name, addedByAdditionalProperties),
            onBlur,
            onFocus,
            registry,
            disabled,
            readonly,
            hideError,
            onDropPropertyClick: parent.onDropPropertyClick,
        }
    }

    if (fieldPath || component || children) {
        contentProps.uiSchema["ui:layout"] = {
            ...layout,
            "path": fieldPath
        }
        contentProps.uiSchema["ui:onlyChildren"] = (!!fieldPath || name === '.' || (children || []).length)
    } else {
        contentProps = assign(contentProps, others)
    }
    let element = React.createElement(SchemaField, contentProps)
    return Object.keys(element.props.schema).length ? element : null
}

export function LayoutElement({id: key, layout, render}) {
    const {
        component,
        props: props_ = {},
        eprops = {},
        fprops = {},
        vprops = {},
        children,
        force_render
    } = layout;
    const {formContext: {FormContext}} = render
    const {form} = useContext(FormContext)
    let elements = (children || []).map((element, index) => {
            if (isObject(element)) {
                return createLayoutElement({
                    key: `${key}-${index}`, render, layout: element
                })
            }
            return element
        }),
        type = getComponents({render, component}),
        domain = getComponentDomains({render, component});

    const props = useMemo(() => {
        let props = cloneDeepWith(props_, customizerCloneDeep)
        Object.entries(eprops).forEach(([path, layout], index) => {
            set(props, path, createLayoutElement({
                key: `${key}-ele-${index}`,
                layout,
                render
            }))
        });
        Object.entries(fprops).forEach(([path, func]) => {
            set(props, path, form.compileFunc(func).bind(null, render, layout))
        });
        Object.entries(vprops).forEach(([path, func]) => {
            set(props, path, form.compileFunc(func)(render, layout))
        });
        return props;
    }, [eprops, fprops, vprops, form, form.state, form.state.formData, props_, render, layout, key])

    props.key = key
    if (type) {
        props.render = render
    } else {
        type = "div"
    }
    if (domain && !domain({...props, children: elements})) {
        return null
    }
    if (elements.filter(v => v !== null).length) {
        return <Suspense key={key}>
            {React.createElement(type, props, elements)}
        </Suspense>
    } else if (force_render) {
        return <Suspense key={key}>
            {React.createElement(type, props)}
        </Suspense>
    } else {
        return null
    }

}


var components = {};


export function registerComponent(name, component) {
    components[name] = component
}

var domains = {};


export function registerComponentDomain(name, domain) {
    domains[name] = domain
}

function fixLayoutOption(obj) {
    if (obj && (obj["ui:option"] || {}).layout) {
        if (!obj.hasOwnProperty("ui:layout"))
            obj["ui:layout"] = obj["ui:option"].layout
        delete obj["ui:option"]["layout"]
    }
    return obj
}

