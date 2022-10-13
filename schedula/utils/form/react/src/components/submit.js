import {Button} from '@mui/material';


export default function _submit(props) {
    return (
        <Button key="submit" type="submit" {...props}>
            {props.children || "submit"}
        </Button>
    );
}