import React, {useState} from "react";
import ErrorIcon from "@mui/icons-material/Error";
import CloseIcon from "@mui/icons-material/Close";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import {
    Snackbar,
    Badge,
    Alert,
    Stack,
    AlertTitle
} from "@mui/material";
import IconButton from '@mui/material/IconButton';

const ErrorList = ({errors}) => {
    const [open, setOpen] = useState(false);
    const setToggle = () => {
        setOpen(!open)
    };
    return (
        <Snackbar
            anchorOrigin={{vertical: 'bottom', horizontal: 'right'}}
            open={true}
            onClose={() => {
            }}
            key={'error'}
        >
            <div>{!open ? (
                    <IconButton onClick={setToggle}>
                        <Badge color="error"
                               badgeContent={errors.length} max={99}>
                            <ErrorIcon/>
                        </Badge>
                    </IconButton>) :
                (<Stack
                    direction="row"
                    justifyContent="flex-end"
                    alignItems="flex-end"
                    spacing={0}>
                    <Alert severity="error">
                        <AlertTitle>Errors</AlertTitle>
                        <List dense={true}
                              sx={{maxWidth: "50%", maxHeight: "30vh"}}>
                            {errors.map((error, i) => (
                                    <ListItem key={i}>{error.stack}</ListItem>
                                )
                            )}
                        </List>
                    </Alert>
                    <IconButton color="inherit" size="small"
                                onClick={setToggle}>
                        <CloseIcon/>
                    </IconButton>
                </Stack>)}</div>
        </Snackbar>

    );
};

export default ErrorList;