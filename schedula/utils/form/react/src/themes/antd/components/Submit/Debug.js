import {Button} from 'antd';


const SubmitDebug = ({children, render, ...props}) => {
    const {formContext} = render
    const {form} = formContext
    return <Button
        type="primary"
        onClick={() => {
            form.onSubmit(null, {headers: {Debug: true}})
        }} {...props}>
        {children || "debug"}
    </Button>
}


export default SubmitDebug;
