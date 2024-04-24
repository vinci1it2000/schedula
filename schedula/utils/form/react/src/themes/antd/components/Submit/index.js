import {Button} from 'antd';


const Submit = ({children, render, ...props}) => {
    const {formContext} = render
    const {form} = formContext
    return <Button
        type="primary"
        onClick={(event) => {
            event.preventDefault()
            form.onSubmit(null, {})
        }} {...props}>
        {children || "submit"}
    </Button>
}

export default Submit;
