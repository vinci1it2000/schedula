import {Templates} from "@rjsf/antd"
import {
    FieldTemplate as coreFieldTemplate
} from "../../../../core/templates/FieldTemplate";


export default function FieldTemplate(props) {
    return coreFieldTemplate({
        Templates: {
            FieldTemplate: Templates.FieldTemplate
        }, ...props
    })
}
