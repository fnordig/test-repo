use std::{fs, path::Path};

use rusqlite::{Connection, OpenFlags, TransactionBehavior, config::DbConfig};
use tempfile::tempdir;
use walkdir::WalkDir;

type Result<T, E = Box<dyn std::error::Error>> = std::result::Result<T, E>;

fn setup(conn: &mut Connection) -> Result<()> {
    conn.execute_batch(
        "
             -- we unconditionally want write-ahead-logging mode
             PRAGMA journal_mode = WAL;
             -- Sync at the most criticial moments, but not with every write
             PRAGMA synchronous = NORMAL;
             -- limit size of the journal. TODO(bug 2049290): value currently arbitrary.
             -- needs refinement.
             PRAGMA journal_size_limit = 512000; -- 512 KB.
             -- We don't care about temp tables being persisted to disk
             PRAGMA temp_store = MEMORY;
             -- allows adding incremental cleanup later
             PRAGMA auto_vacuum = INCREMENTAL;
            ",
    )?;

    // Set hardening flags.
    conn.set_db_config(DbConfig::SQLITE_DBCONFIG_DEFENSIVE, true)?;

    // Turn off misfeatures: double-quoted strings and untrusted schemas.
    conn.set_db_config(DbConfig::SQLITE_DBCONFIG_DQS_DML, false)?;
    conn.set_db_config(DbConfig::SQLITE_DBCONFIG_DQS_DDL, false)?;
    conn.set_db_config(DbConfig::SQLITE_DBCONFIG_TRUSTED_SCHEMA, true)?;

    conn.execute_batch("CREATE TABLE data(val TEXT);")?;

    Ok(())
}

#[test]
fn test() {
    run().unwrap();
}

fn list_dir(path: &Path) -> Result<()> {
    for entry in WalkDir::new(path) {
        eprintln!("{}", entry?.path().display());
    }

    Ok(())
}

fn insert(conn: &mut Connection, val: i32) -> Result<()> {
    eprintln!("inserting {val}");
    conn.execute("INSERT INTO data (val) VALUES (?1)", (val,))?;
    Ok(())
}

fn run() -> Result<()> {
    let tmp = tempdir()?;

    let flags = OpenFlags::SQLITE_OPEN_NO_MUTEX
        | OpenFlags::SQLITE_OPEN_EXRESCODE
        | OpenFlags::SQLITE_OPEN_CREATE
        | OpenFlags::SQLITE_OPEN_READ_WRITE;

    dbg!(&tmp);

    let db_dir = tmp.path().join("db");
    fs::create_dir_all(&db_dir)?;

    let path = db_dir.join("glean.db");
    dbg!(&path);

    let mut conn = Connection::open_with_flags(path, flags)?;
    setup(&mut conn)?;

    {
        let tx = conn.transaction_with_behavior(TransactionBehavior::Exclusive)?;
        tx.execute_batch(&format!("PRAGMA user_version = {}", 1))?;
        tx.commit()?;
    }

    insert(&mut conn, 1)?;

    eprintln!("list 1");
    list_dir(tmp.path())?;

    eprintln!("removing db_dir");
    fs::remove_dir_all(&db_dir).unwrap_or_else(|err| {
        eprintln!("remove_dir_all failed: {err:?}")
    });
    eprintln!("list 2");
    list_dir(tmp.path())?;

    insert(&mut conn, 2).unwrap_or_else(|err| {
        eprintln!("insert failed: {err:?}");
    });

    drop(conn);

    eprintln!("list 3");
    list_dir(tmp.path())?;

    fs::remove_dir_all(&db_dir).unwrap_or_else(|err| {
        eprintln!("2 remove_dir_all failed: {err:?}")
    });

    eprintln!("list 4");
    list_dir(tmp.path())?;

    Ok(())
}
