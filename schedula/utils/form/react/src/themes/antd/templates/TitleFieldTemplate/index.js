import {Templates} from "@rjsf/antd"
import {
    TitleFieldTemplate as coreTitleFieldTemplate
} from "../../../../core/templates/TitleFieldTemplate";
import InfoFieldTemplate from './InfoFieldTemplate'

export default function TitleFieldTemplate(props) {
    return coreTitleFieldTemplate({
        Templates: {...Templates, InfoFieldTemplate},
        ...props
    })
}