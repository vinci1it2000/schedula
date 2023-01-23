import {Tooltip} from "antd";
import {QuestionCircleOutlined} from "@ant-design/icons"
import {getUiOptions} from "@rjsf/utils";

export default function InfoFieldTemplate({uiSchema}) {
    const {info} = getUiOptions(uiSchema);
    const icon = <QuestionCircleOutlined style={{
        color: "rgba(0, 0, 0, 0.45)",
        cursor: "help",
        "writingMode": " horizontal-tb",
        "marginInlineStart": "4px"
    }}/>

    return info ? <Tooltip title={info}>{icon} </Tooltip> : null
}