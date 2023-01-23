import formatMd from '../../utils/Markdown'

export default function ValueWidget({value, options, formContext, ...props}) {
    const {form} = formContext
    const {format, markdown} = options
    if (markdown) {
        return formatMd({
            children: [markdown],
            formData: value,
            form,
            formContext, ...props
        })
    }
    if (format) {
        return form.n(value, format);
    }
    return value
}