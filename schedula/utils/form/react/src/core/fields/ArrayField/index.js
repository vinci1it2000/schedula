import {getDefaultRegistry} from "@rjsf/core";
import {getUiOptions} from "@rjsf/utils";
import {createLayoutElement} from "../utils";

const baseRegistry = getDefaultRegistry()

export default class ArrayField extends baseRegistry.fields.ArrayField {
    render() {
        const {layout} = getUiOptions(this.props.uiSchema);
        if (layout) {
            const {
                schema: rawSchema,
                uiSchema = {},
                formData,
                errorSchema,
                idSchema,
                disabled = false,
                readonly = false,
                hideError,
                idPrefix,
                name,
                idSeparator = '_',
                onBlur,
                onFocus,
                autofocus,
                rawErrors,
                registry: registry_,
            } = this.props;
            const {fields, formContext: formContext_, schemaUtils} = registry_;
            const formContext = {...formContext_, parent: this}
            const registry = {...registry_, formContext}
            const {SchemaField} = fields;
            const schema = schemaUtils.retrieveSchema(rawSchema, formData);
            return createLayoutElement({
                key: idSchema.$id,
                layout,
                render: {
                    readonly,
                    disabled,
                    idSchema,
                    uiSchema,
                    schema,
                    name,
                    formData,
                    formContext,
                    registry,
                    errorSchema,
                    idPrefix,
                    idSeparator,
                    onBlur,
                    onFocus,
                    hideError,
                    autofocus,
                    parent: this,
                    SchemaField,
                    rawErrors
                },
                isArray: true
            })
        } else {
            return super.render()
        }
    }
}
