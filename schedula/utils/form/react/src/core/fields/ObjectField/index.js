import {getUiOptions} from "@rjsf/utils";
import {createLayoutElement} from "../utils";
import {getDefaultRegistry} from "@rjsf/core"

const {fields: {ObjectField: BaseObjectField}} = getDefaultRegistry()

class ObjectField extends BaseObjectField {
    constructor(props) {
        super(props);
        const {formContext} = this.props.registry;
        this.props.registry.formContext = {...formContext, parent: this}
    }

    render() {
        const {uiSchema = {}} = this.props;
        const {layout} = getUiOptions(uiSchema);
        if (layout) {
            const {
                schema: rawSchema,
                formData,
                errorSchema,
                idSchema,
                disabled = false,
                readonly = false,
                hideError,
                idPrefix,
                idSeparator,
                onBlur,
                onFocus,
                registry,
            } = this.props;
            const {fields, formContext, schemaUtils} = registry;
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
                    formData,
                    formContext,
                    registry,
                    errorSchema,
                    idPrefix,
                    idSeparator,
                    onBlur,
                    onFocus,
                    hideError,
                    parent: this,
                    SchemaField
                }
            })
        } else {
            return super.render()
        }

    }
}

export default ObjectField;