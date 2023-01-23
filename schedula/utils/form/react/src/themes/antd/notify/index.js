import {notification} from "antd";

export default function notify({type = 'error', ...props}) {
    notification[type]({placement: 'top', ...props})
}